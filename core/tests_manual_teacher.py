"""Integration tests: run `py manage.py test core.tests_manual_teacher` after patch."""
from django.test import TestCase
from django.urls import reverse

from core.models import (
    AcademicBlock, Batch, Department, Faculty, FacultySubject,
    Floor, Room, Subject, TimetableEntry, User,
)


class TeacherManualSchedulingTests(TestCase):
    def setUp(self):
        self.dep = Department.objects.create(name='Engineering', code='TESTENG')
        block = AcademicBlock.objects.create(name='Test building', code='TB')
        floor = Floor.objects.create(block=block, floor_number=1)
        self.room1 = Room.objects.create(floor=floor, room_number='R1', capacity=30, room_type='classroom')
        self.room2 = Room.objects.create(floor=floor, room_number='R2', capacity=30, room_type='classroom')
        self.batch = Batch.objects.create(department=self.dep, year=1, semester=1, section='A', strength=20)
        self.batch2 = Batch.objects.create(department=self.dep, year=1, semester=1, section='B', strength=20)
        self.subject = Subject.objects.create(name='Math', code='TM101', department=self.dep, subject_type='theory', weekly_frequency=3, duration_hours=1)
        self.user = User.objects.create_user(username='my_teacher', password='test_pass_123', role='teacher')
        self.other = User.objects.create_user(username='other_teacher', password='test_pass_123', role='teacher')
        self.student = User.objects.create_user(username='my_student', password='test_pass_123', role='student')
        self.faculty = Faculty.objects.create(user=self.user, name='Teacher One', employee_id='T001', department=self.dep)
        self.faculty2 = Faculty.objects.create(user=self.other, name='Teacher Two', employee_id='T002', department=self.dep)
        FacultySubject.objects.create(faculty=self.faculty, subject=self.subject, batch=self.batch)
        FacultySubject.objects.create(faculty=self.faculty2, subject=self.subject, batch=self.batch2)
        self.data = {
            'batch': self.batch.pk, 'subject': self.subject.pk, 'faculty': self.faculty2.pk, # forged; server must override
            'room': self.room1.pk, 'day_of_week': 0, 'start_time': 10, 'end_time': 11,
        }

    def test_teacher_can_create_only_as_self(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('manual_entry_create'), self.data)
        self.assertEqual(response.status_code, 302)
        saved = TimetableEntry.objects.get()
        self.assertEqual(saved.faculty, self.faculty)
        self.assertTrue(saved.is_fixed)

    def test_student_cannot_add(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse('manual_entry_create'), self.data).status_code, 403)
        self.assertFalse(TimetableEntry.objects.exists())

    def test_cannot_create_in_other_batch(self):
        self.client.force_login(self.user)
        data = {**self.data, 'batch': self.batch2.pk}
        response = self.client.post(reverse('manual_entry_create'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TimetableEntry.objects.exists())

    def test_existing_room_conflict_rejected(self):
        TimetableEntry.objects.create(batch=self.batch2, subject=self.subject, faculty=self.faculty2, room=self.room1, day_of_week=0, start_time=10, end_time=11)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('manual_entry_create'), self.data).status_code, 200)
        self.assertEqual(TimetableEntry.objects.count(), 1)

    def test_room_change_works(self):
        TimetableEntry.objects.create(batch=self.batch2, subject=self.subject, faculty=self.faculty2, room=self.room1, day_of_week=0, start_time=10, end_time=11)
        self.client.force_login(self.user)
        response = self.client.post(reverse('manual_entry_create'), {**self.data, 'room': self.room2.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TimetableEntry.objects.count(), 2)

    def test_cannot_edit_another_teacher_entry(self):
        entry = TimetableEntry.objects.create(batch=self.batch2, subject=self.subject, faculty=self.faculty2, room=self.room1, day_of_week=0, start_time=10, end_time=11)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('manual_entry_delete', args=[entry.pk])).status_code, 403)
        self.assertTrue(TimetableEntry.objects.filter(pk=entry.pk).exists())

    def test_own_entry_can_be_edited(self):
        entry = TimetableEntry.objects.create(batch=self.batch, subject=self.subject, faculty=self.faculty, room=self.room1, day_of_week=0, start_time=10, end_time=11)
        self.client.force_login(self.user)
        response = self.client.post(reverse('manual_entry_edit', args=[entry.pk]), {**self.data, 'room': self.room2.pk})
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.room, self.room2)
