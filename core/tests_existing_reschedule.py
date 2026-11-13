"""Regression checks for moving an existing class instead of creating duplicates.

Run: .\\venv\\Scripts\\python.exe manage.py test core.tests_existing_reschedule -v 2
Uses Django's isolated test database, not db.sqlite3.
"""
from django.test import TestCase
from django.urls import reverse

from core.models import (
    AcademicBlock, Batch, Department, Faculty, FacultySubject,
    Floor, Room, Subject, TimetableEntry, User,
)


class ExistingLessonRescheduleTests(TestCase):
    def setUp(self):
        department = Department.objects.create(name='Test Engineering', code='TER')
        building = AcademicBlock.objects.create(name='Testing Building', code='BTR')
        floor = Floor.objects.create(block=building, floor_number=1)
        self.room1 = Room.objects.create(floor=floor, room_number='R1', capacity=30, room_type='classroom')
        self.room2 = Room.objects.create(floor=floor, room_number='R2', capacity=30, room_type='classroom')
        self.batch1 = Batch.objects.create(department=department, year=1, semester=1, section='AA', strength=20)
        self.batch2 = Batch.objects.create(department=department, year=1, semester=1, section='BB', strength=20)
        self.subject = Subject.objects.create(department=department, name='Test Physics',
                                              code='TEST-PHYS', subject_type='theory',
                                              duration_hours=1, weekly_frequency=2)
        self.admin = User.objects.create_user(username='reschedule_admin', role='admin', password='p@ss-for-test')
        self.user = User.objects.create_user(username='reschedule_teacher', role='teacher', password='p@ss-for-test')
        self.other_user = User.objects.create_user(username='another_teacher', role='teacher', password='p@ss-for-test')
        self.faculty = Faculty.objects.create(name='Teacher Monday', department=department,
                                               employee_id='TMON', user=self.user)
        self.other_faculty = Faculty.objects.create(name='Teacher Friday', department=department,
                                                     employee_id='TFRI', user=self.other_user)
        FacultySubject.objects.create(faculty=self.faculty, batch=self.batch1, subject=self.subject)
        FacultySubject.objects.create(faculty=self.other_faculty, batch=self.batch2, subject=self.subject)
        self.monday = TimetableEntry.objects.create(batch=self.batch1, subject=self.subject, faculty=self.faculty,
                                                      room=self.room2, day_of_week=0, start_time=17, end_time=18,
                                                      is_fixed=True)
        self.friday = TimetableEntry.objects.create(batch=self.batch2, subject=self.subject,
                                                     faculty=self.other_faculty, room=self.room2,
                                                     day_of_week=4, start_time=17, end_time=18,
                                                     is_fixed=True)

    def update_fields(self, **changes):
        data = dict(batch=self.batch1.pk, subject=self.subject.pk, faculty=self.faculty.pk,
                    room=self.room2.pk, day_of_week=0, start_time=17, end_time=18)
        data.update(changes)
        return data

    def test_reschedule_form_initializes_from_existing_entry(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('manual_entry_edit', args=[self.monday.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Editing existing class #{self.monday.pk}')
        self.assertEqual(response.context['form'].instance.pk, self.monday.pk)
        self.assertEqual(response.context['form'].instance.day_of_week, 0)

    def test_monday_move_to_free_friday_preserves_id_and_row_count(self):
        self.client.force_login(self.admin)
        original_count = TimetableEntry.objects.count()
        response = self.client.post(reverse('manual_entry_edit', args=[self.monday.pk]),
                                    self.update_fields(day_of_week=4, start_time=16, end_time=17))
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'?batch={self.batch1.pk}', response.url)
        self.monday.refresh_from_db()
        self.assertEqual((self.monday.day_of_week, self.monday.start_time, self.monday.end_time), (4, 16, 17))
        self.assertEqual(TimetableEntry.objects.count(), original_count, 'Moving must never add a new row')
        self.friday.refresh_from_db()
        self.assertEqual((self.friday.day_of_week, self.friday.start_time), (4, 17))

    def test_collision_blocks_update_without_duplicate(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('manual_entry_edit', args=[self.monday.pk]),
                                    self.update_fields(day_of_week=4, start_time=17, end_time=18))
        self.assertEqual(response.status_code, 200)
        self.monday.refresh_from_db()
        self.assertEqual((self.monday.day_of_week, self.monday.start_time), (0, 17))
        self.assertEqual(TimetableEntry.objects.count(), 2)
        self.assertContains(response, 'Scheduling conflict')

    def test_conflict_suggestion_moves_existing_record_not_create(self):
        self.client.force_login(self.admin)
        original_pk = self.monday.pk
        form_url = reverse('manual_entry_edit', args=[self.monday.pk])
        response = self.client.post(form_url, self.update_fields(day_of_week=4, start_time=17, end_time=18,
                                                                  preview='1'))
        self.assertEqual(response.status_code, 200)
        opts = response.context['suggestions']
        self.assertTrue(opts, 'Expected alternatives to the occupied Friday room')
        self.assertEqual(TimetableEntry.objects.count(), 2)
        # Any allowed direct alternative should update exactly the same PK.
        proposal = next(o for o in opts if o['kind'] in ('room', 'time', 'day'))
        applied = self.client.post(form_url, {'apply_suggestion': proposal['token']})
        self.assertEqual(applied.status_code, 302)
        self.assertEqual(TimetableEntry.objects.count(), 2)
        self.monday.refresh_from_db()
        self.assertEqual(self.monday.pk, original_pk)
        self.assertNotEqual((self.monday.day_of_week, self.monday.start_time, self.monday.room_id),
                            (0, 17, self.room2.pk))

    def test_edit_link_only_shows_for_authorized_user(self):
        self.client.force_login(self.admin)
        view_url = reverse('timetable_view') + f'?batch={self.batch1.pk}'
        response = self.client.get(view_url)
        self.assertContains(response, reverse('manual_entry_edit', args=[self.monday.pk]))
        self.client.force_login(self.other_user)
        response = self.client.get(view_url)
        self.assertNotContains(response, reverse('manual_entry_edit', args=[self.monday.pk]))
        self.assertEqual(self.client.get(reverse('manual_entry_edit', args=[self.monday.pk])).status_code, 403)

    def test_delete_requires_post_and_just_removes_selected_id(self):
        self.client.force_login(self.admin)
        delete_url = reverse('manual_entry_delete', args=[self.friday.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'?batch={self.batch2.pk}', response.url)
        self.assertFalse(TimetableEntry.objects.filter(pk=self.friday.pk).exists())
        self.assertTrue(TimetableEntry.objects.filter(pk=self.monday.pk).exists())
