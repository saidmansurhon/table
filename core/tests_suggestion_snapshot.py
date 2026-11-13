"""Regression test for stale snapshots when proposing moves from ModelForm.
Uses the in-memory Django test DB, not the user's db.sqlite3.
"""
from django.test import TestCase
from django.urls import reverse
from core.models import TimetableEntry
from core.tests_existing_reschedule import ExistingLessonRescheduleTests


class SuggestionSnapshotTests(TestCase):
    setUp = ExistingLessonRescheduleTests.setUp
    update_fields = ExistingLessonRescheduleTests.update_fields

    def test_changed_form_does_not_corrupt_original_snapshot(self):
        """POST preview Friday request; signed snapshot must still represent Monday."""
        self.client.force_login(self.admin)
        initial_count = TimetableEntry.objects.count()
        original_pk = self.monday.pk
        url = reverse('manual_entry_edit', args=[self.monday.pk])
        response = self.client.post(url, self.update_fields(
            day_of_week=4, start_time=17, end_time=18, preview='1'))
        self.assertEqual(response.status_code, 200)
        options = response.context['suggestions']
        self.assertTrue(options)
        # A proposal should work immediately; it must update, not duplicate.
        choice = next(o for o in options if o['kind'] in ('room', 'time', 'day'))
        applied = self.client.post(url, {'apply_suggestion': choice['token']})
        self.assertEqual(applied.status_code, 302, applied.content.decode()[:1000])
        self.assertEqual(TimetableEntry.objects.count(), initial_count)
        self.monday.refresh_from_db()
        self.assertEqual(self.monday.pk, original_pk)

    def test_really_changed_record_rejects_stale_proposal(self):
        self.client.force_login(self.admin)
        url = reverse('manual_entry_edit', args=[self.monday.pk])
        resp = self.client.post(url, self.update_fields(day_of_week=4, start_time=17, end_time=18, preview='1'))
        self.assertEqual(resp.status_code, 200)
        choice = next(o for o in resp.context['suggestions'] if o['kind'] in ('room', 'time', 'day'))
        self.monday.start_time = 15
        self.monday.end_time = 16
        self.monday.save(update_fields=['start_time', 'end_time'])
        rejected = self.client.post(url, {'apply_suggestion': choice['token']})
        self.assertEqual(rejected.status_code, 200)
        self.monday.refresh_from_db()
        self.assertEqual((self.monday.start_time, self.monday.end_time), (15, 16))
