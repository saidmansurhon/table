"""Manual timetable editor for faculty and timetable coordinators.

This module intentionally does not call the automatic OR-Tools generator.
"""
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Batch, CombinedClass, Faculty, FacultySubject, Room, Subject, TimetableEntry


EDIT_ROLES = {'admin', 'coordinator', 'class_advisor', 'teacher'}


def teacher_faculty(user):
    if user.role != 'teacher':
        return None
    return Faculty.objects.filter(user=user).first()


def can_manage_entry(user, entry):
    if entry.combined_class_id:
        # Combined classes need a dedicated multi-batch editor.
        return False
    if user.is_superuser or user.role in ('admin', 'coordinator'):
        return True
    if user.role == 'teacher':
        faculty = teacher_faculty(user)
        return bool(faculty and entry.faculty_id == faculty.pk)
    if user.role == 'class_advisor':
        profile = getattr(user, 'class_advisor_profile', None)
        return bool(profile and entry.batch_id == profile.batch_id)
    return False


def overlapping_entries(day, start, end, *, exclude_pk=None):
    result = TimetableEntry.objects.filter(
        day_of_week=day, start_time__lt=end, end_time__gt=start
    ).select_related('faculty', 'batch', 'room')
    if exclude_pk:
        result = result.exclude(pk=exclude_pk)
    return result


def free_room_names(batch, day, start, end):
    """Small human-readable suggestion for a room-only collision."""
    if batch.fixed_room_id:
        return []
    occupied = set(overlapping_entries(day, start, end).values_list('room_id', flat=True))
    occupied.update(CombinedClass.objects.filter(
        day_of_week=day, start_time__lt=end, end_time__gt=start
    ).values_list('room_id', flat=True))
    rooms = Room.objects.filter(is_allocatable=True, capacity__gte=batch.strength)
    return [str(room) for room in rooms.exclude(pk__in=occupied)[:5]]


class ManualEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ('batch', 'subject', 'faculty', 'room', 'day_of_week', 'start_time', 'end_time')
        widgets = {
            'batch': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'faculty': forms.Select(attrs={'class': 'form-input'}),
            'room': forms.Select(attrs={'class': 'form-input'}),
            'day_of_week': forms.Select(attrs={'class': 'form-input'}),
            'start_time': forms.NumberInput(attrs={'class': 'form-input', 'min': 10, 'max': 17}),
            'end_time': forms.NumberInput(attrs={'class': 'form-input', 'min': 11, 'max': 18}),
        }

    def __init__(self, *args, user, skip_conflicts=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.skip_conflicts = skip_conflicts
        self.fields['room'].queryset = Room.objects.filter(is_allocatable=True)
        assignments = FacultySubject.objects.all()

        if user.role == 'teacher':
            faculty = teacher_faculty(user)
            faculty_qs = Faculty.objects.filter(pk=faculty.pk) if faculty else Faculty.objects.none()
            self.fields['faculty'].queryset = faculty_qs
            self.fields['faculty'].widget = forms.HiddenInput()
            if faculty:
                self.fields['faculty'].initial = faculty.pk
                assignments = assignments.filter(faculty=faculty)
            else:
                assignments = assignments.none()
        elif user.role == 'class_advisor':
            profile = getattr(user, 'class_advisor_profile', None)
            assignments = assignments.filter(batch_id=profile.batch_id) if profile else assignments.none()

        self.fields['batch'].queryset = Batch.objects.filter(
            id__in=assignments.values('batch_id')
        ).distinct()
        self.fields['subject'].queryset = Subject.objects.filter(
            id__in=assignments.values('subject_id')
        ).distinct()
        if user.role != 'teacher':
            self.fields['faculty'].queryset = Faculty.objects.filter(
                id__in=assignments.values('faculty_id')
            ).distinct()

    def clean(self):
        data = super().clean()
        batch = data.get('batch')
        subject = data.get('subject')
        faculty = data.get('faculty')
        room = data.get('room')
        day = data.get('day_of_week')
        start = data.get('start_time')
        end = data.get('end_time')

        if all((batch, subject, faculty)) and not FacultySubject.objects.filter(
            batch=batch, subject=subject, faculty=faculty
        ).exists():
            self.add_error(None, 'This teacher is not assigned to this subject for this batch.')

        if not all(x is not None for x in (batch, subject, faculty, room, day, start, end)):
            return data

        if start >= end:
            self.add_error('end_time', 'End time must be later than start time.')
            return data
        if end - start != subject.duration_hours:
            self.add_error('end_time', f'This subject requires {subject.duration_hours} hour(s).')

        if room.capacity < batch.strength:
            self.add_error('room', f'The room holds {room.capacity}, but the batch has {batch.strength} students.')
        if batch.fixed_room_id and batch.fixed_room_id != room.pk:
            self.add_error('room', 'This batch has a fixed room; choose that room.')
        if batch.shift_id:
            shift = batch.shift
            if start < shift.start_time or end > shift.end_time:
                self.add_error('start_time', 'The class must be inside the batch shift.')
            lunch_end = shift.lunch_start + shift.lunch_duration
            if start < lunch_end and end > shift.lunch_start:
                self.add_error('start_time', 'The class overlaps the lunch break.')

        if self.skip_conflicts:
            return data

        collisions = []
        for other in overlapping_entries(day, start, end, exclude_pk=self.instance.pk):
            reasons = []
            if other.room_id == room.pk:
                reasons.append('room')
            if other.faculty_id == faculty.pk:
                reasons.append('teacher')
            if other.batch_id == batch.pk:
                reasons.append('batch')
            if reasons:
                collisions.append(f"{other.subject.code} ({other.start_time}:00–{other.end_time}:00): {', '.join(reasons)}")
                if len(collisions) == 5:
                    break

        # CombinedClass may not yet have corresponding TimetableEntry records.
        combined = CombinedClass.objects.filter(
            day_of_week=day, start_time__lt=end, end_time__gt=start
        ).filter(Q(room=room) | Q(faculty=faculty) | Q(batches=batch)).distinct()
        for other in combined[:5]:
            reasons = []
            if other.room_id == room.pk:
                reasons.append('room')
            if other.faculty_id == faculty.pk:
                reasons.append('teacher')
            if other.batches.filter(pk=batch.pk).exists():
                reasons.append('batch')
            if reasons:
                collisions.append(f"Combined {other.subject.code}: {', '.join(reasons)}")

        if collisions:
            advice = ''
            if not any(('teacher' in c or 'batch' in c) for c in collisions):
                names = free_room_names(batch, day, start, end)
                if names:
                    advice = ' Free rooms at the same time: ' + '; '.join(names) + '.'
            self.add_error(None, 'Scheduling conflict: ' + ' | '.join(collisions) + '.' + advice)
        return data


def _allowed(user):
    return user.is_superuser or user.role in EDIT_ROLES


def _prepare_form_data(request):
    data = request.POST.copy()
    if request.user.role == 'teacher':
        faculty = teacher_faculty(request.user)
        if faculty:
            # Ignore any client-supplied teacher ID.
            data['faculty'] = str(faculty.pk)
    return data


def _redirect_after_change(user, batch_id):
    if user.role == 'teacher':
        return redirect('teacher_schedule')
    return redirect(reverse('timetable_view') + f'?batch={batch_id}')


def _entry_form_view(request, *, instance=None):
    """Existing Django form + human-approved, signed suggestions."""
    from .suggestions_django import apply_signed_suggestion, form_suggestions

    title = f'Edit / Reschedule class #{instance.pk}' if instance else 'Add class manually' 
    if request.method == 'POST' and request.POST.get('apply_suggestion'):
        try:
            saved = apply_signed_suggestion(request.user, request.POST['apply_suggestion'], entry=instance)
        except ValidationError as exc:
            messages.error(request, 'Cannot apply suggestion: ' + '; '.join(exc.messages))
        else:
            messages.success(request, f'Existing class #{saved.pk} moved after conflict re-check.'
                                      if instance else 'New class created from a checked suggestion.')
            return _redirect_after_change(request.user, saved.batch_id)
        form = ManualEntryForm(user=request.user, instance=instance)
        return render(request, 'forms/timetable_entry_form.html', {'form': form, 'title': title, 'editing_entry': instance})

    if request.method == 'POST':
        form = ManualEntryForm(_prepare_form_data(request), user=request.user, instance=instance)
        is_valid = form.is_valid()
        if is_valid and request.POST.get('preview') != '1':
            with transaction.atomic():
                # Revalidation in the transaction avoids stale UI results.
                form = ManualEntryForm(_prepare_form_data(request), user=request.user, instance=instance)
                if form.is_valid():
                    entry = form.save(commit=False)
                    entry.is_fixed = True
                    entry.save()
                    messages.success(request, f'Existing class #{entry.pk} updated.'
                                             if instance else 'New class added.')
                    return _redirect_after_change(request.user, entry.batch_id)
        options = form_suggestions(form, request.user, entry=instance)
    else:
        initial = {}
        if request.GET.get('batch', '').isdigit():
            initial['batch'] = int(request.GET['batch'])
        form = ManualEntryForm(user=request.user, instance=instance, initial=initial)
        options = []
    return render(request, 'forms/timetable_entry_form.html', {
        'form': form, 'title': title, 'suggestions': options,
        'suggestions_requested': request.method == 'POST',
        'editing_entry': instance,
    })


@login_required
def manual_entry_create(request):
    if not _allowed(request.user):
        return HttpResponseForbidden('Permission denied.')
    if request.user.role == 'teacher' and not teacher_faculty(request.user):
        messages.error(request, 'Your teacher account is not linked to a Faculty record. Contact the administrator.')
        return redirect('teacher_schedule')
    return _entry_form_view(request)

@login_required
def teacher_schedule(request):
    if not _allowed(request.user):
        return HttpResponseForbidden('Permission denied.')
    entries = TimetableEntry.objects.select_related('faculty', 'batch', 'subject', 'room')
    if request.user.role == 'teacher':
        faculty = teacher_faculty(request.user)
        entries = entries.filter(faculty=faculty) if faculty else entries.none()
    elif request.user.role == 'class_advisor':
        profile = getattr(request.user, 'class_advisor_profile', None)
        entries = entries.filter(batch_id=profile.batch_id) if profile else entries.none()
    return render(request, 'timetable/my_schedule.html', {
        'entries': entries.order_by('day_of_week', 'start_time'),
        'has_teacher_link': (teacher_faculty(request.user) is not None) if request.user.role == 'teacher' else True,
    })


@login_required
def manual_entry_edit(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk)
    if not can_manage_entry(request.user, entry):
        return HttpResponseForbidden('Permission denied.')
    return _entry_form_view(request, instance=entry)


@login_required
def manual_entry_delete(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    with transaction.atomic():
        entry = get_object_or_404(TimetableEntry, pk=pk)
        if not can_manage_entry(request.user, entry):
            return HttpResponseForbidden('Permission denied.')
        batch_id = entry.batch_id
        entry.delete()
    messages.success(request, 'Class removed.')
    return _redirect_after_change(request.user, batch_id)
