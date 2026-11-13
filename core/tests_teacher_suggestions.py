"""Scenario tests for room/time/day proposals, swaps, and verified persistence."""
from django.test import TestCase
from django.urls import reverse

from core.models import (AcademicBlock, Batch, Department, Faculty,
                         FacultySubject, Floor, Room, Subject,
                         TimetableEntry, User)


class SuggestionWorkflowTests(TestCase):
    def setUp(self):
        dep = Department.objects.create(name='Test engineering', code='ENGX')
        block = AcademicBlock.objects.create(name='Test', code='TX')
        floor = Floor.objects.create(block=block, floor_number=1)
        self.r1 = Room.objects.create(floor=floor, room_number='101', capacity=30, room_type='classroom')
        self.r2 = Room.objects.create(floor=floor, room_number='102', capacity=30, room_type='classroom')
        self.r3 = Room.objects.create(floor=floor, room_number='103', capacity=30, room_type='classroom')
        self.b1 = Batch.objects.create(department=dep, year=1, semester=1, section='A', strength=20)
        self.b2 = Batch.objects.create(department=dep, year=1, semester=1, section='B', strength=20)
        self.subject = Subject.objects.create(department=dep, name='Math', code='MTT101',
                                              subject_type='theory', weekly_frequency=2, duration_hours=1)
        self.admin = User.objects.create_user(username='test_admin', password='abc123!', role='admin')
        self.u1 = User.objects.create_user(username='t1', password='abc123!', role='teacher')
        self.u2 = User.objects.create_user(username='t2', password='abc123!', role='teacher')
        self.f1 = Faculty.objects.create(user=self.u1, name='First teacher', employee_id='TF1', department=dep)
        self.f2 = Faculty.objects.create(user=self.u2, name='Second teacher', employee_id='TF2', department=dep)
        FacultySubject.objects.create(faculty=self.f1, batch=self.b1, subject=self.subject)
        FacultySubject.objects.create(faculty=self.f2, batch=self.b2, subject=self.subject)
        self.blocker = TimetableEntry.objects.create(batch=self.b2, subject=self.subject,
                faculty=self.f2, room=self.r1, day_of_week=0, start_time=10, end_time=11, is_fixed=True)
        self.data = dict(batch=self.b1.pk, subject=self.subject.pk, faculty=self.f1.pk,
                         room=self.r1.pk, day_of_week=0, start_time=10, end_time=11)

    def _proposals(self, user, url=None, data=None):
        self.client.force_login(user)
        resp = self.client.post(url or reverse('manual_entry_create'), data or self.data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('suggestions', resp.context)
        return resp.context['suggestions']

    def test_room_suggestion_requires_teacher_confirmation(self):
        options = self._proposals(self.u1)
        room = next(p for p in options if p['kind'] == 'room')
        self.assertEqual(TimetableEntry.objects.count(), 1)  # preview did not change the DB
        response = self.client.post(reverse('manual_entry_create'), {'apply_suggestion': room['token']})
        self.assertEqual(response.status_code, 302)
        created = TimetableEntry.objects.exclude(pk=self.blocker.pk).get()
        self.assertNotEqual(created.room_id, self.r1.pk)
        self.assertEqual((created.day_of_week, created.start_time), (0, 10))

    def test_teacher_cannot_move_others_class(self):
        options = self._proposals(self.u1)
        self.assertFalse(any(p['kind'] in {'swap', 'move_blocker'} for p in options))
        self.blocker.refresh_from_db()
        self.assertEqual(self.blocker.room_id, self.r1.pk)

    def test_admin_can_approve_move_of_blocker(self):
        options = self._proposals(self.admin)
        moving = next(p for p in options if p['kind'] == 'move_blocker')
        response = self.client.post(reverse('manual_entry_create'), {'apply_suggestion': moving['token']})
        self.assertEqual(response.status_code, 302)
        self.blocker.refresh_from_db()
        self.assertNotEqual((self.blocker.day_of_week, self.blocker.start_time, self.blocker.room_id), (0, 10, self.r1.pk))
        new_class = TimetableEntry.objects.exclude(pk=self.blocker.pk).get()
        self.assertEqual((new_class.day_of_week, new_class.start_time, new_class.room_id), (0, 10, self.r1.pk))

    def test_expired_or_stale_solution_cannot_overwrite(self):
        options = self._proposals(self.admin)
        move = next(p for p in options if p['kind'] == 'move_blocker')
        self.blocker.room = self.r2
        self.blocker.save(update_fields=['room'])
        resp = self.client.post(reverse('manual_entry_create'), {'apply_suggestion': move['token']})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TimetableEntry.objects.count(), 1)

    def test_teacher_conflict_not_resolved_by_room_only(self):
        self.blocker.faculty = self.f1
        self.blocker.save(update_fields=['faculty'])
        options = self._proposals(self.u1)
        self.assertFalse(any(p['kind'] == 'room' for p in options))

    def test_swapping_two_classes_requires_confirm(self):
        original = TimetableEntry.objects.create(batch=self.b1, subject=self.subject,
                faculty=self.f1, room=self.r2, day_of_week=1, start_time=12, end_time=13, is_fixed=True)
        opts = self._proposals(self.admin, reverse('manual_entry_edit', args=[original.pk]), self.data)
        swap = next(p for p in opts if p['kind'] == 'swap')
        resp = self.client.post(reverse('manual_entry_edit', args=[original.pk]), {'apply_suggestion': swap['token']})
        self.assertEqual(resp.status_code, 302)
        original.refresh_from_db()
        self.blocker.refresh_from_db()
        self.assertEqual((original.day_of_week, original.start_time, original.room_id), (0, 10, self.r1.pk))
        self.assertEqual((self.blocker.day_of_week, self.blocker.start_time, self.blocker.room_id), (1, 12, self.r2.pk))
