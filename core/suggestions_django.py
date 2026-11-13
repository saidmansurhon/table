"""Django adapter for the human-approved conflict suggestions workflow.

Calls are synchronous and no changes are made until the user clicks Apply.
"""
from dataclasses import replace

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CombinedClass, FacultySubject, Room, TimetableEntry
from .suggestion_engine import Lesson, Position, RoomInfo, collisions, suggest, valid

TOKEN_SALT = 'university-timetable-teacher-suggestions-v1'
TOKEN_MAX_AGE = 15 * 60


def _shift(batch):
    s = batch.shift
    return (s.start_time, s.end_time, s.lunch_start, s.lunch_start + s.lunch_duration) if s else None


def _lesson(entry, *, movable=False):
    return Lesson(f'entry:{entry.pk}', frozenset([entry.batch_id]), entry.faculty_id,
                  entry.subject_id, Position(entry.day_of_week, entry.start_time, entry.end_time, entry.room_id),
                  entry.batch.strength, entry.batch.fixed_room_id, _shift(entry.batch), movable)


def _wanted(cleaned, *, key):
    batch = cleaned['batch']
    return Lesson(key, frozenset([batch.pk]), cleaned['faculty'].pk, cleaned['subject'].pk,
                  Position(cleaned['day_of_week'], cleaned['start_time'], cleaned['end_time'], cleaned['room'].pk),
                  batch.strength, batch.fixed_room_id, _shift(batch), False)


def _load(user):
    from .manual_schedule import teacher_faculty
    ordinary = list(TimetableEntry.objects.filter(combined_class__isnull=True)
                    .select_related('batch__shift', 'faculty', 'subject', 'room'))
    by_pk = {item.pk: item for item in ordinary}
    teacher = teacher_faculty(user) if user.role == 'teacher' else None
    advisor = getattr(user, 'class_advisor_profile', None) if user.role == 'class_advisor' else None
    def authorized(entry):
        if user.is_superuser or user.role in ('admin', 'coordinator'):
            return True
        if user.role == 'teacher':
            return bool(teacher and entry.faculty_id == teacher.pk)
        if user.role == 'class_advisor':
            return bool(advisor and entry.batch_id == advisor.batch_id)
        return False
    scheduled = [_lesson(entry, movable=authorized(entry)) for entry in ordinary]

    # Some combined classes have mirrored rows in TimetableEntry. Count once only.
    combined = CombinedClass.objects.select_related('subject', 'faculty', 'room').prefetch_related('batches__shift')
    for item in combined:
        batches = list(item.batches.all())
        scheduled.append(Lesson(f'combined:{item.pk}', frozenset(b.pk for b in batches),
                                item.faculty_id, item.subject_id,
                                Position(item.day_of_week, item.start_time, item.end_time, item.room_id),
                                sum(b.strength for b in batches), None, None, False))
    rooms = [RoomInfo(r.pk, f'Room {r.room_number} (capacity {r.capacity})', r.capacity,
                      r.is_allocatable) for r in Room.objects.all()]
    return scheduled, by_pk, rooms


def _fingerprint(entry):
    if entry is None:
        return None
    return [entry.pk, entry.batch_id, entry.subject_id, entry.faculty_id,
            entry.room_id, entry.day_of_week, entry.start_time, entry.end_time]


def _serial_position(p):
    return [p.day, p.start, p.end, p.room]


def _parse_position(values):
    return Position(*values)


def _clean_fields(cleaned):
    return {key: cleaned[key].pk for key in ('batch', 'subject', 'faculty', 'room')} | {
        key: int(cleaned[key]) for key in ('day_of_week', 'start_time', 'end_time')}


def _describes(p):
    return {
        'room': 'Another room, same time',
        'time': 'Another time',
        'day': 'Another day',
        'move_blocker': 'Move the blocking class',
        'swap': 'Swap two classes',
    }.get(p.kind, 'Alternative')


def form_suggestions(form, user, *, entry=None):
    """Return signed action proposals. Never takes unvalidated raw POST fields."""
    keys = ('batch', 'subject', 'faculty', 'room', 'day_of_week', 'start_time', 'end_time')
    cleaned = form.cleaned_data
    if any(cleaned.get(key) is None for key in keys):
        return []
    if not FacultySubject.objects.filter(batch=cleaned['batch'], subject=cleaned['subject'],
                                         faculty=cleaned['faculty']).exists():
        return []
    wanted = _wanted(cleaned, key=f'entry:{entry.pk}' if entry else 'draft:0')
    scheduled, originals, rooms = _load(user)
    original = next((lesson for lesson in scheduled if entry and lesson.key == f'entry:{entry.pk}'), None)
    # A validated ModelForm may have mutated `entry` in memory before save().
    # Obtain the optimistic-lock fingerprint from a fresh DB instance instead.
    # The pending form fields remain in `cleaned` and are signed separately.
    db_entry = TimetableEntry.objects.filter(pk=entry.pk).first() if entry else None
    original_db_fingerprint = _fingerprint(db_entry)
    result = []
    for p in suggest(wanted, scheduled, rooms, original=original):
        data = _clean_fields(cleaned)
        data.update(room=p.target.room, day_of_week=p.target.day,
                    start_time=p.target.start, end_time=p.target.end)
        blocker_pk = int(p.blocker_key.split(':')[1]) if p.blocker_key else None
        blocker = originals.get(blocker_pk)
        token = signing.dumps({
            'user': user.pk, 'edit': entry.pk if entry else 0,
            'original': original_db_fingerprint, 'fields': data,
            'blocker': blocker_pk, 'blocker_original': _fingerprint(blocker),
            'blocker_position': _serial_position(p.blocker_new) if p.blocker_new else None,
        }, salt=TOKEN_SALT, compress=True)
        readable_label = p.label
        if blocker:
            readable_label = readable_label.replace(f'entry:{blocker.pk}',
                f'{blocker.subject.code} / {blocker.faculty.name} / {blocker.batch}')
        result.append({'kind': p.kind, 'heading': _describes(p), 'label': readable_label,
                       'token': token, 'score': p.score})
    return result


def apply_signed_suggestion(user, token, *, entry=None):
    """Revalidate current timetable and permissions inside transaction before applying."""
    from .manual_schedule import ManualEntryForm, can_manage_entry, teacher_faculty
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired) as error:
        raise ValidationError('The suggestion has expired. Please search again.') from error
    if payload.get('user') != user.pk or payload.get('edit') != (entry.pk if entry else 0):
        raise ValidationError('This suggestion does not belong to this request.')
    data = payload['fields']
    if set(data) != {'batch', 'subject', 'faculty', 'room', 'day_of_week', 'start_time', 'end_time'}:
        raise ValidationError('Invalid suggestion.')

    with transaction.atomic():
        target_obj = (TimetableEntry.objects.select_for_update().select_related('batch__shift')
                      .filter(pk=entry.pk).first()) if entry else None
        if entry and (not target_obj or _fingerprint(target_obj) != payload['original']
                      or not can_manage_entry(user, target_obj)):
            raise ValidationError('This class has changed. Please request new suggestions.')
        if user.role == 'teacher':
            faculty = teacher_faculty(user)
            if not faculty or faculty.pk != data['faculty']:
                raise ValidationError('Teachers may schedule only their own classes.')

        blocker_pk = payload.get('blocker')
        blocker = None
        if blocker_pk:
            blocker = (TimetableEntry.objects.select_for_update().select_related('batch__shift')
                       .filter(pk=blocker_pk, combined_class__isnull=True).first())
            if (not blocker or not can_manage_entry(user, blocker)
                    or _fingerprint(blocker) != payload.get('blocker_original')
                    or not payload.get('blocker_position')):
                raise ValidationError('The blocking class changed or cannot be moved by your account.')

        # Normal ModelForm structural validation; conflict check is deferred for a two-lesson move.
        form = ManualEntryForm(data, user=user, instance=target_obj,
                               skip_conflicts=bool(blocker))
        if not form.is_valid():
            raise ValidationError('The suggested slot is no longer permitted: ' + str(form.errors))

        scheduled, _, rooms = _load(user)
        candidate = _wanted(form.cleaned_data, key=f'entry:{target_obj.pk}' if target_obj else 'draft:0')
        excludes = set()
        if target_obj:
            excludes.add(f'entry:{target_obj.pk}')
        if blocker:
            excludes.add(f'entry:{blocker.pk}')
        if not valid(candidate, scheduled, rooms, exclude=excludes):
            raise ValidationError('Another lesson now occupies the suggested time or room.')

        new_blocker = None
        if blocker:
            new_pos = _parse_position(payload['blocker_position'])
            current = _lesson(blocker)
            new_blocker = replace(current, position=new_pos)
            if not valid(new_blocker, scheduled, rooms, exclude=excludes):
                raise ValidationError('The blocking class cannot move to that slot anymore.')
            if collisions(new_blocker, [candidate]):
                raise ValidationError('The two changed classes would still conflict.')
            blocker.room_id = new_pos.room
            blocker.day_of_week = new_pos.day
            blocker.start_time = new_pos.start
            blocker.end_time = new_pos.end
            blocker.save(update_fields=['room', 'day_of_week', 'start_time', 'end_time'])

        saved = form.save(commit=False)
        saved.is_fixed = True
        saved.save()
        return saved
