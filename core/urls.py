from django.urls import path
from . import views
from . import manual_schedule

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Infrastructure
    path('blocks/', views.block_list, name='block_list'),
    path('blocks/create/', views.block_create, name='block_create'),
    path('blocks/<int:pk>/edit/', views.block_edit, name='block_edit'),
    path('blocks/<int:pk>/delete/', views.block_delete, name='block_delete'),
    path('blocks/<int:block_pk>/floors/add/', views.floor_create, name='floor_create'),
    path('floors/<int:pk>/delete/', views.floor_delete, name='floor_delete'),

    path('rooms/', views.room_list, name='room_list'),
    path('rooms/create/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/edit/', views.room_edit, name='room_edit'),
    path('rooms/<int:pk>/delete/', views.RoomDeleteView.as_view(), name='room_delete'),

    # Academic
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.DepartmentEditView.as_view(), name='department_edit'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department_delete'),

    path('shifts/', views.shift_list, name='shift_list'),
    path('shifts/create/', views.shift_create, name='shift_create'),
    path('shifts/<int:pk>/edit/', views.shift_edit, name='shift_edit'),
    path('shifts/<int:pk>/delete/', views.shift_delete, name='shift_delete'),

    path('batches/', views.batch_list, name='batch_list'),
    path('batches/create/', views.batch_create, name='batch_create'),
    path('batches/subjects/', views.batch_subjects_view, name='batch_subjects_view'),
    path('batches/upload-csv/', views.batch_subject_upload_csv, name='batch_subject_upload_csv'),
    path('batches/<int:pk>/edit/', views.batch_edit, name='batch_edit'),
    path('batches/<int:pk>/delete/', views.BatchDeleteView.as_view(), name='batch_delete'),
    path('batches/<int:pk>/', views.batch_detail, name='batch_detail'),

    path('faculty/', views.faculty_list, name='faculty_list'),
    path('faculty/create/', views.faculty_create, name='faculty_create'),
    path('faculty/upload-csv/', views.faculty_upload_csv, name='faculty_upload_csv'),
    path('faculty/<int:pk>/edit/', views.FacultyEditView.as_view(), name='faculty_edit'),
    path('faculty/<int:pk>/delete/', views.FacultyDeleteView.as_view(), name='faculty_delete'),

    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/upload-csv/', views.subject_upload_csv, name='subject_upload_csv'),
    path('subjects/<int:pk>/edit/', views.SubjectEditView.as_view(), name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.SubjectDeleteView.as_view(), name='subject_delete'),

    path('faculty-subjects/', views.faculty_subject_list, name='faculty_subject_list'),
    path('faculty-subjects/create/', views.faculty_subject_create, name='faculty_subject_create'),
    path('faculty-subjects/upload-csv/', views.upload_faculty_subject_csv, name='upload_faculty_subject'),

    # Timetable
    path('timetable/generate/', views.generate_timetable, name='generate_timetable'),
    path('timetable/generate-all/', views.generate_all_timetables, name='generate_all_timetables'),
    path('timetable/view/', views.timetable_view, name='timetable_view'),
    path('timetable/manual-entry/', views.manual_entry_create, name='manual_entry_create'),
    path('timetable/my-schedule/', manual_schedule.teacher_schedule, name='teacher_schedule'),
    path('timetable/manual-entry/<int:pk>/edit/', manual_schedule.manual_entry_edit, name='manual_entry_edit'),
    path('timetable/manual-entry/<int:pk>/delete/', manual_schedule.manual_entry_delete, name='manual_entry_delete'),
    path('timetable/combined/', views.combined_class_list, name='combined_class_list'),
    path('timetable/combined/create/', views.combined_class_create, name='combined_class_create'),
    path('timetable/combined/<int:pk>/edit/', views.combined_class_edit, name='combined_class_edit'),
    path('timetable/combined/<int:pk>/delete/', views.combined_class_delete, name='combined_class_delete'),

    # Saved Timetables
    path('timetable/saved/', views.saved_timetable_list, name='saved_timetable_list'),
    path('timetable/saved/<int:pk>/', views.saved_timetable_view, name='saved_timetable_view'),
    path('timetable/saved/<int:pk>/delete/', views.saved_timetable_delete, name='saved_timetable_delete'),

    # Class Advisors
    path('advisors/', views.class_advisor_list, name='class_advisor_list'),
    path('advisors/create/', views.class_advisor_create, name='class_advisor_create'),
    path('advisors/<int:pk>/reset-password/', views.class_advisor_reset_password, name='class_advisor_reset_password'),
    path('advisors/<int:pk>/delete/', views.class_advisor_delete, name='class_advisor_delete'),

    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.student_create, name='student_create'),
    path('students/upload-csv/', views.student_upload_csv, name='student_upload_csv'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('my-timetable/', views.student_timetable, name='student_timetable'),
]
