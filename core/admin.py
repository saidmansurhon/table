from django.contrib import admin
from .models import (
    User, AcademicBlock, Floor, Room, Department, Batch, 
    Faculty, Subject, FacultySubject, TimetableEntry, TimetableGeneration, BatchSubject
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'role', 'is_staff']
    list_filter = ['role', 'is_staff']
    search_fields = ['username', 'email']

@admin.register(AcademicBlock)
class AcademicBlockAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']

@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ['block', 'floor_number']
    list_filter = ['block']

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'floor', 'room_type', 'capacity', 'is_allocatable']
    list_filter = ['room_type', 'is_allocatable', 'floor__block']
    search_fields = ['room_number']

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['department', 'year', 'semester', 'section', 'strength', 'fixed_room']
    list_filter = ['department', 'year', 'semester']
    search_fields = ['section']

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ['name', 'employee_id', 'department', 'email', 'user']
    list_filter = ['department']
    search_fields = ['name', 'employee_id', 'email']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'subject_type', 'weekly_frequency', 'department']
    list_filter = ['subject_type', 'department']
    search_fields = ['code', 'name']

@admin.register(FacultySubject)
class FacultySubjectAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'subject', 'batch']
    list_filter = ['faculty', 'subject']

@admin.register(BatchSubject)
class BatchSubjectAdmin(admin.ModelAdmin):
    list_display = ['batch', 'subject']
    list_filter = ['batch', 'subject']

@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ['batch', 'subject', 'faculty', 'room', 'day_of_week', 'start_time', 'is_fixed']
    list_filter = ['day_of_week', 'is_fixed', 'batch']
    search_fields = ['subject__code', 'faculty__name']

@admin.register(TimetableGeneration)
class TimetableGenerationAdmin(admin.ModelAdmin):
    list_display = ['id', 'generated_by', 'status', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at', 'completed_at']
