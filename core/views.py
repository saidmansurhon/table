from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
import csv
import io
from .models import (
    AcademicBlock, Floor, Room, Department, Batch, Faculty, 
    Subject, FacultySubject, FacultySubjectCapability, TimetableEntry, TimetableGeneration,
    BatchSubject, CombinedClass, SavedTimetable, SavedTimetableEntry, ClassAdvisor, User, Student, Shift
)
from .forms import (
    AcademicBlockForm, FloorForm, RoomForm, DepartmentForm, 
    BatchForm, FacultyForm, SubjectForm, FacultySubjectForm, TimetableEntryForm,
    FacultyCSVUploadForm, SubjectCSVUploadForm, BatchSubjectCSVUploadForm, FacultySubjectCSVUploadForm,
    CombinedClassForm, ShiftForm
)
from scheduler_engine.solver import TimetableSolver


# ── Mixins ────────────────────────────────────────────────────────────────────

class RoleRequiredMixin(LoginRequiredMixin):
    """CBV mixin: restrict access to specific roles."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            messages.error(request, "You don't have permission to access this page.")
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class SuccessMessageMixin:
    """Adds a success message after form_valid."""
    success_message = ''

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


# ── Helper decorator (kept for FBVs) ──────────────────────────────────────────

def role_required(allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                messages.error(request, "You don't have permission to access this page.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ── AcademicBlock CBVs ────────────────────────────────────────────────────────

class BlockEditView(RoleRequiredMixin, SuccessMessageMixin, UpdateView):
    model = AcademicBlock
    form_class = AcademicBlockForm
    template_name = 'forms/block_form.html'
    success_url = reverse_lazy('block_list')
    allowed_roles = ['admin']
    success_message = 'Academic block updated successfully.'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Edit Block'
        return ctx


class BlockDeleteView(RoleRequiredMixin, DeleteView):
    model = AcademicBlock
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('block_list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type'] = 'Academic Block'
        return ctx

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Academic block deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ── Room CBVs ─────────────────────────────────────────────────────────────────

class RoomDeleteView(RoleRequiredMixin, DeleteView):
    model = Room
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('room_list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type'] = 'Room'
        return ctx

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Room deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ── Department CBVs ───────────────────────────────────────────────────────────

class DepartmentEditView(RoleRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'forms/department_form.html'
    success_url = reverse_lazy('department_list')
    allowed_roles = ['admin', 'coordinator']
    success_message = 'Department updated successfully.'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Edit Department'
        return ctx


class DepartmentDeleteView(RoleRequiredMixin, DeleteView):
    model = Department
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('department_list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type'] = 'Department'
        return ctx

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Department deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ── Batch CBVs ────────────────────────────────────────────────────────────────

class BatchDeleteView(RoleRequiredMixin, DeleteView):
    model = Batch
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('batch_list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type'] = 'Batch'
        return ctx

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Batch deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ── Faculty CBVs ──────────────────────────────────────────────────────────────

class FacultyEditView(RoleRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Faculty
    form_class = FacultyForm
    template_name = 'forms/faculty_form.html'
    success_url = reverse_lazy('faculty_list')
    allowed_roles = ['admin', 'coordinator', 'class_advisor']
    success_message = 'Faculty updated successfully.'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Edit Faculty'
        return ctx


class FacultyDeleteView(RoleRequiredMixin, DeleteView):
    model = Faculty
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('faculty_list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type'] = 'Faculty'
        return ctx

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Faculty deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ── Subject CBVs ──────────────────────────────────────────────────────────────

class SubjectEditView(RoleRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'forms/subject_form.html'
    success_url = reverse_lazy('subject_list')
    allowed_roles = ['admin', 'coordinator', 'class_advisor']
    success_message = 'Subject updated successfully.'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Edit Subject'
        return ctx


class SubjectDeleteView(RoleRequiredMixin, DeleteView):
    model = Subject
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('subject_list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type'] = 'Subject'
        return ctx

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Subject deleted successfully.')
        return super().delete(request, *args, **kwargs)



def landing_page(request):
    if request.user.is_authenticated:
        return redirect('/app/')
    return render(request, 'landing.html')


@login_required
def dashboard(request):
    # Students go directly to their timetable
    if request.user.role == 'student':
        return redirect('student_timetable')
    if request.user.role == 'teacher':
        return redirect('teacher_schedule')
    context = {
        'total_batches': Batch.objects.count(),
        'total_faculty': Faculty.objects.count(),
        'total_subjects': Subject.objects.count(),
        'total_rooms': Room.objects.filter(is_allocatable=True).count(),
        'recent_generations': TimetableGeneration.objects.all()[:5],
    }
    return render(request, 'dashboard.html', context)


# Infrastructure Views
@login_required
@role_required(['admin'])
def block_list(request):
    blocks = AcademicBlock.objects.all()
    return render(request, 'infrastructure/block_list.html', {'blocks': blocks})


@login_required
@role_required(['admin'])
def block_create(request):
    if request.method == 'POST':
        form = AcademicBlockForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Academic block created successfully.')
            return redirect('block_list')
    else:
        form = AcademicBlockForm()
    return render(request, 'forms/block_form.html', {'form': form, 'title': 'Create Block'})


@login_required
@role_required(['admin'])
def block_edit(request, pk):
    block = get_object_or_404(AcademicBlock, pk=pk)
    if request.method == 'POST':
        form = AcademicBlockForm(request.POST, instance=block)
        if form.is_valid():
            form.save()
            messages.success(request, 'Academic block updated successfully.')
            return redirect('block_list')
    else:
        form = AcademicBlockForm(instance=block)
    return render(request, 'forms/block_form.html', {'form': form, 'title': 'Edit Block'})


@login_required
@role_required(['admin'])
def block_delete(request, pk):
    block = get_object_or_404(AcademicBlock, pk=pk)
    if request.method == 'POST':
        block.delete()
        messages.success(request, 'Academic block deleted successfully.')
        return redirect('block_list')
    return render(request, 'confirm_delete.html', {'object': block, 'type': 'Block'})


@login_required
@role_required(['admin'])
def floor_create(request, block_pk):
    block = get_object_or_404(AcademicBlock, pk=block_pk)
    if request.method == 'POST':
        form = FloorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Floor added to {block.name} successfully.')
            return redirect('block_list')
    else:
        form = FloorForm(initial={'block': block})
    return render(request, 'forms/floor_form.html', {'form': form, 'title': f'Add Floor to {block.name}', 'block': block})


@login_required
@role_required(['admin'])
def floor_delete(request, pk):
    floor = get_object_or_404(Floor, pk=pk)
    block_pk = floor.block.pk
    if request.method == 'POST':
        floor.delete()
        messages.success(request, 'Floor deleted successfully.')
        return redirect('block_list')
    return render(request, 'confirm_delete.html', {'object': floor, 'type': 'Floor'})


@login_required
@role_required(['admin'])
def room_list(request):
    rooms = Room.objects.select_related('floor__block').all()
    return render(request, 'infrastructure/room_list.html', {'rooms': rooms})


@login_required
@role_required(['admin'])
def room_create(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Room created successfully.')
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'forms/room_form.html', {'form': form, 'title': 'Create Room'})


@login_required
@role_required(['admin'])
def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'Room updated successfully.')
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)
    return render(request, 'forms/room_form.html', {'form': form, 'title': 'Edit Room'})


# Department Views
@login_required
def department_list(request):
    departments = Department.objects.all()
    return render(request, 'academic/department_list.html', {'departments': departments})


@login_required
@role_required(['admin', 'coordinator'])
def department_create(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department created successfully.')
            return redirect('department_list')
    else:
        form = DepartmentForm()
    return render(request, 'forms/department_form.html', {'form': form, 'title': 'Create Department'})


# Batch Views
@login_required
def batch_list(request):
    batches = Batch.objects.select_related('department', 'fixed_room').all()
    return render(request, 'academic/batch_list.html', {'batches': batches})


@login_required
@role_required(['admin', 'coordinator'])
def batch_create(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Batch created successfully.')
            return redirect('batch_list')
    else:
        form = BatchForm()
    return render(request, 'forms/batch_form.html', {'form': form, 'title': 'Create Batch'})


@login_required
@role_required(['admin', 'coordinator'])
def batch_edit(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, 'Batch updated successfully.')
            return redirect('batch_list')
    else:
        form = BatchForm(instance=batch)
    return render(request, 'forms/batch_form.html', {'form': form, 'title': 'Edit Batch'})


@login_required
def batch_detail(request, pk):
    batch = get_object_or_404(Batch, pk=pk)

    # Subjects from BatchSubject (CSV) + FacultySubject mappings, deduplicated
    bs_subject_ids = set(BatchSubject.objects.filter(batch=batch).values_list('subject_id', flat=True))
    fs_subject_ids = set(FacultySubject.objects.filter(batch=batch).values_list('subject_id', flat=True))
    all_subject_ids = bs_subject_ids | fs_subject_ids
    all_subjects = Subject.objects.filter(id__in=all_subject_ids).order_by('code')

    batch_subjects_with_status = [
        {'subject': s, 'has_faculty': s.id in fs_subject_ids}
        for s in all_subjects
    ]
    return render(request, 'academic/batch_detail.html', {
        'batch': batch,
        'batch_subjects': batch_subjects_with_status,
        'batch_subjects_with_status': batch_subjects_with_status,
    })


@login_required
def batch_subjects_view(request):
    selected_department = request.GET.get('department')
    selected_year = request.GET.get('year')
    selected_semester = request.GET.get('semester')

    batches = Batch.objects.select_related('department').all()
    if selected_department:
        batches = batches.filter(department_id=selected_department)
    if selected_year:
        batches = batches.filter(year=selected_year)
    if selected_semester:
        batches = batches.filter(semester=selected_semester)

    batches_data = []
    for batch in batches:
        bs_ids = set(BatchSubject.objects.filter(batch=batch).values_list('subject_id', flat=True))
        fs_ids = set(FacultySubject.objects.filter(batch=batch).values_list('subject_id', flat=True))
        all_ids = bs_ids | fs_ids
        subjects = list(Subject.objects.filter(id__in=all_ids).order_by('code'))
        if subjects:
            batches_data.append({'batch': batch, 'subjects': subjects})

    context = {
        'batches_data': batches_data,
        'has_data': len(batches_data) > 0,
        'departments': Department.objects.all(),
        'selected_department': selected_department,
        'selected_year': selected_year,
        'selected_semester': selected_semester,
    }
    return render(request, 'academic/batch_subjects_view.html', context)


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def batch_subject_upload_csv(request):
    if request.method == 'POST':
        form = BatchSubjectCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            department = form.cleaned_data['department']
            year = form.cleaned_data['year']
            semester = form.cleaned_data['semester']
            
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                created_batches = 0
                updated_batches = 0
                linked_subjects = 0
                errors = []
                
                for idx, row in enumerate(reader, start=2):
                    section = row.get('section', '').strip()
                    
                    if not section:
                        errors.append(f"Row {idx}: section is required")
                        continue
                    
                    batch, created = Batch.objects.get_or_create(
                        department=department,
                        year=year,
                        semester=semester,
                        section=section,
                        defaults={'strength': 60, 'max_classes_per_day': 6}
                    )
                    
                    if created:
                        created_batches += 1
                    else:
                        updated_batches += 1
                    
                    # Process subject codes
                    for key, value in row.items():
                        if key.startswith('subject-code') and value.strip():
                            subject_code = value.strip()
                            try:
                                subject = Subject.objects.get(code=subject_code)
                                _, link_created = BatchSubject.objects.get_or_create(batch=batch, subject=subject)
                                if link_created:
                                    linked_subjects += 1
                            except Subject.DoesNotExist:
                                # Try case-insensitive match
                                subject_qs = Subject.objects.filter(code__iexact=subject_code)
                                if subject_qs.exists():
                                    subject = subject_qs.first()
                                    _, link_created = BatchSubject.objects.get_or_create(batch=batch, subject=subject)
                                    if link_created:
                                        linked_subjects += 1
                                else:
                                    errors.append(f"Row {idx}: Subject '{subject_code}' not found")
                
                if errors:
                    messages.warning(request, f'Created {created_batches} batches, updated {updated_batches} batches, linked {linked_subjects} new subjects. Errors: {"; ".join(errors[:5])}')
                else:
                    messages.success(request, f'Successfully created {created_batches} batches, updated {updated_batches} batches, and linked {linked_subjects} new subjects.')
                return redirect('batch_list')
            
            except Exception as e:
                messages.error(request, f'Error processing CSV: {str(e)}')
    else:
        form = BatchSubjectCSVUploadForm()
    
    all_subjects = Subject.objects.all().order_by('code')
    return render(request, 'forms/batch_subject_csv_upload.html', {'form': form, 'title': 'Upload Batch-Subject CSV', 'all_subjects': all_subjects})


# Faculty Views
@login_required
def faculty_list(request):
    faculty = Faculty.objects.select_related('department').all()
    return render(request, 'academic/faculty_list.html', {'faculty': faculty})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def faculty_create(request):
    if request.method == 'POST':
        form = FacultyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculty created successfully.')
            return redirect('faculty_list')
    else:
        form = FacultyForm()
    return render(request, 'forms/faculty_form.html', {'form': form, 'title': 'Create Faculty'})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def faculty_upload_csv(request):
    if request.method == 'POST':
        form = FacultyCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            department = form.cleaned_data['department']
            
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                created_count = 0
                skipped_count = 0
                errors = []
                
                for idx, row in enumerate(reader, start=2):
                    teacher_name = row.get('Teach-name', '').strip()
                    employee_id = row.get('Emp-ID', '').strip()
                    email = row.get('email', '').strip()
                    
                    if not teacher_name:
                        errors.append(f"Row {idx}: Teach-name is required")
                        continue
                    
                    if not employee_id:
                        errors.append(f"Row {idx}: Emp-ID is required")
                        continue
                    
                    if not Faculty.objects.filter(employee_id=employee_id).exists():
                        Faculty.objects.create(
                            name=teacher_name,
                            employee_id=employee_id,
                            department=department,
                            email=email,
                            max_hours_per_week=20
                        )
                        created_count += 1
                    else:
                        skipped_count += 1
                
                if errors:
                    messages.warning(request, f'Created {created_count} faculty. Errors: {"; ".join(errors[:5])}')
                else:
                    messages.success(request, f'Successfully created {created_count} faculty members. Skipped {skipped_count} duplicates.')
                return redirect('faculty_list')
            
            except Exception as e:
                messages.error(request, f'Error processing CSV: {str(e)}')
    else:
        form = FacultyCSVUploadForm()
    
    return render(request, 'forms/faculty_csv_upload.html', {'form': form, 'title': 'Upload Faculty CSV'})


# Subject Views
@login_required
def subject_list(request):
    subjects = Subject.objects.select_related('department').all()
    return render(request, 'academic/subject_list.html', {'subjects': subjects})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully.')
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'forms/subject_form.html', {'form': form, 'title': 'Create Subject'})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def subject_upload_csv(request):
    if request.method == 'POST':
        form = SubjectCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            department = form.cleaned_data['department']
            subject_type = form.cleaned_data['subject_type']
            duration_hours = form.cleaned_data['duration_hours']
            
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                created_count = 0
                skipped_count = 0
                errors = []
                
                for idx, row in enumerate(reader, start=2):
                    subject_code = row.get('subject-code', '').strip()
                    subject_name = row.get('subject-name', '').strip()
                    weekly_frequency = row.get('weekly-frequency', '').strip()
                    
                    if not subject_code:
                        errors.append(f"Row {idx}: subject-code is required")
                        continue
                    
                    if not subject_name:
                        errors.append(f"Row {idx}: subject-name is required")
                        continue
                    
                    if not weekly_frequency:
                        errors.append(f"Row {idx}: weekly-frequency is required")
                        continue
                    
                    try:
                        weekly_frequency = int(weekly_frequency)
                    except ValueError:
                        errors.append(f"Row {idx}: weekly-frequency must be a number")
                        continue
                    
                    if not Subject.objects.filter(code=subject_code).exists():
                        Subject.objects.create(
                            name=subject_name,
                            code=subject_code,
                            subject_type=subject_type,
                            weekly_frequency=weekly_frequency,
                            duration_hours=duration_hours,
                            department=department
                        )
                        created_count += 1
                    else:
                        skipped_count += 1
                
                if errors:
                    messages.warning(request, f'Created {created_count} subjects. Errors: {"; ".join(errors[:5])}')
                else:
                    messages.success(request, f'Successfully created {created_count} subjects. Skipped {skipped_count} duplicates.')
                return redirect('subject_list')
            
            except Exception as e:
                messages.error(request, f'Error processing CSV: {str(e)}')
    else:
        form = SubjectCSVUploadForm()
    
    return render(request, 'forms/subject_csv_upload.html', {'form': form, 'title': 'Upload Subject CSV'})


# Faculty-Subject Mapping
@login_required
def faculty_subject_list(request):
    capability_mappings = FacultySubjectCapability.objects.select_related('faculty', 'subject').all()
    batch_mappings = FacultySubject.objects.select_related('faculty', 'subject', 'batch').all()
    return render(request, 'academic/faculty_subject_list.html', {
        'mappings': batch_mappings,
        'capability_mappings': capability_mappings,
        'batch_mappings': batch_mappings,
    })


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def faculty_subject_create(request):
    if request.method == 'POST':
        form = FacultySubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculty-Subject mapping created successfully.')
            return redirect('faculty_subject_list')
    else:
        form = FacultySubjectForm()
    return render(request, 'forms/faculty_subject_form.html', {'form': form, 'title': 'Create Mapping'})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def upload_faculty_subject_csv(request):
    form = FacultySubjectCSVUploadForm(request.POST or None, request.FILES or None)
    created_count = 0
    skipped_count = 0
    errors = []

    if request.method == 'POST' and form.is_valid():
        try:
            decoded = request.FILES['csv_file'].read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))

            for idx, row in enumerate(reader, start=2):
                emp_id = row.get('faculty_emp_id', '').strip()
                subject_code = row.get('subject_code', '').strip()
                batch_section = row.get('batch_section', '').strip()

                if not emp_id or not subject_code or not batch_section:
                    errors.append(f"Row {idx}: all three columns are required")
                    continue

                try:
                    faculty = Faculty.objects.get(employee_id__iexact=emp_id)
                except Faculty.DoesNotExist:
                    errors.append(f"Row {idx}: Faculty '{emp_id}' not found")
                    continue

                try:
                    subject = Subject.objects.get(code__iexact=subject_code)
                except Subject.DoesNotExist:
                    errors.append(f"Row {idx}: Subject '{subject_code}' not found")
                    continue

                batch = Batch.objects.filter(section__iexact=batch_section).first()
                if not batch:
                    errors.append(f"Row {idx}: Batch section '{batch_section}' not found")
                    continue

                _, created = FacultySubject.objects.get_or_create(
                    faculty=faculty, subject=subject, batch=batch
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

            if errors:
                messages.warning(request, f"Created {created_count}, skipped {skipped_count} duplicates. Errors: {'; '.join(errors[:5])}")
            else:
                messages.success(request, f"Successfully created {created_count} mappings. Skipped {skipped_count} duplicates.")

        except Exception as e:
            messages.error(request, f"Error processing CSV: {str(e)}")

    faculty_list_qs = Faculty.objects.select_related('department').order_by('employee_id')
    subject_list_qs = Subject.objects.order_by('code')
    batch_list_qs = Batch.objects.select_related('department').order_by('section')

    return render(request, 'forms/upload_faculty_subject.html', {
        'form': form,
        'title': 'Upload Faculty-Subject Mappings',
        'faculty_list': faculty_list_qs,
        'subject_list': subject_list_qs,
        'batch_list': batch_list_qs,
        'created_count': created_count,
        'skipped_count': skipped_count,
        'errors': errors,
    })


# Timetable Generation
@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def generate_timetable(request):
    # Class advisor can only see/generate for their assigned batch
    if request.user.role == 'class_advisor':
        try:
            advisor_batch = request.user.class_advisor_profile.batch
            batches = Batch.objects.filter(pk=advisor_batch.pk).select_related('department')
        except Exception:
            messages.error(request, 'No batch assigned to your advisor profile.')
            return redirect('dashboard')
    else:
        batches = Batch.objects.select_related('department').all()
    selected_batch_id = request.POST.get('batch_id') or request.GET.get('batch_id')
    selected_batch = None
    missing_mappings = False

    if selected_batch_id:
        selected_batch = Batch.objects.filter(pk=selected_batch_id).first()
        if selected_batch:
            missing_mappings = not FacultySubject.objects.filter(batch=selected_batch).exists()

    if request.method == 'POST' and selected_batch:
        if missing_mappings:
            messages.error(request, f'No Faculty-Subject mappings found for batch "{selected_batch}". Please upload mappings first.')
        else:
            try:
                with transaction.atomic():
                    generation = TimetableGeneration.objects.create(
                        generated_by=request.user,
                        status='processing'
                    )
                    rooms = list(Room.objects.filter(is_allocatable=True))
                    faculty_subjects = list(FacultySubject.objects.filter(batch=selected_batch).select_related('faculty', 'subject', 'batch'))
                    fixed_entries = list(TimetableEntry.objects.filter(is_fixed=True, batch=selected_batch).select_related('batch', 'subject', 'faculty', 'room'))
                    combined_classes = list(CombinedClass.objects.filter(batches=selected_batch).prefetch_related('batches').select_related('subject', 'faculty', 'room'))

                    solver = TimetableSolver(
                        [selected_batch], None, faculty_subjects, rooms, fixed_entries, combined_classes,
                        working_hours=(
                            selected_batch.shift.start_time if selected_batch.shift else 10,
                            selected_batch.shift.end_time if selected_batch.shift else 18
                        ),
                        lunch_start=selected_batch.shift.lunch_start if selected_batch.shift else 13,
                        lunch_duration=selected_batch.shift.lunch_duration if selected_batch.shift else 1
                    )

                    # Block generation if combined class room capacity is insufficient
                    if solver.combined_room_warnings:
                        generation.status = 'failed'
                        generation.save()
                        for warn in solver.combined_room_warnings:
                            messages.error(request, f'⚠ Combined class room capacity issue: {warn}')
                        return render(request, 'timetable/generate.html', {
                            'batches': batches,
                            'selected_batch': selected_batch,
                            'selected_batch_id': selected_batch_id,
                            'missing_mappings': missing_mappings,
                        })

                    warning = solver.validate_inputs()
                    if warning:
                        messages.warning(request, warning)

                    success, message = solver.solve()

                    if success:
                        # --- Snapshot existing timetable before replacing ---
                        existing_entries = list(
                            TimetableEntry.objects.filter(batch=selected_batch)
                            .select_related('subject', 'faculty', 'room', 'combined_class')
                            .prefetch_related('combined_class__batches')
                        )
                        if existing_entries:
                            snapshot = SavedTimetable.objects.create(
                                batch=selected_batch,
                                saved_by=request.user,
                                label=f"{selected_batch} – saved before regeneration on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                            )
                            SavedTimetableEntry.objects.bulk_create([
                                SavedTimetableEntry(
                                    saved_timetable=snapshot,
                                    subject_code=e.subject.code,
                                    subject_name=e.subject.name,
                                    faculty_name=e.faculty.name,
                                    room_number=e.room.room_number,
                                    day_of_week=e.day_of_week,
                                    start_time=e.start_time,
                                    end_time=e.end_time,
                                    is_fixed=e.is_fixed,
                                    is_combined=bool(e.combined_class_id),
                                    combined_batch_sections=', '.join(
                                        b.section for b in e.combined_class.batches.all()
                                    ) if e.combined_class_id else ''
                                )
                                for e in existing_entries
                            ])

                        # Delete old non-fixed, non-combined entries for this batch
                        TimetableEntry.objects.filter(is_fixed=False, batch=selected_batch, combined_class__isnull=True).delete()

                        # Save regular solver entries
                        for entry_data in solver.solution:
                            TimetableEntry.objects.create(
                                batch_id=entry_data['batch_id'],
                                subject_id=entry_data['subject_id'],
                                faculty_id=entry_data['faculty_id'],
                                room_id=entry_data['room_id'],
                                day_of_week=entry_data['day_of_week'],
                                start_time=entry_data['start_time'],
                                end_time=entry_data['end_time'],
                                is_fixed=False
                            )

                        # Upsert combined class entries for this batch
                        TimetableEntry.objects.filter(batch=selected_batch, combined_class__isnull=False).delete()
                        for cc in combined_classes:
                            TimetableEntry.objects.create(
                                batch=selected_batch,
                                subject=cc.subject,
                                faculty=cc.faculty,
                                room=cc.room,
                                day_of_week=cc.day_of_week,
                                start_time=cc.start_time,
                                end_time=cc.end_time,
                                is_fixed=True,
                                combined_class=cc
                            )

                        generation.status = 'completed'
                        generation.completed_at = timezone.now()
                        generation.save()
                        messages.success(request, f'Timetable generated successfully for {selected_batch}!')
                        return redirect(f'/app/timetable/view/?batch={selected_batch.pk}')
                    else:
                        generation.status = 'failed'
                        generation.error_message = message
                        generation.save()
                        messages.error(request, message)
            except Exception as e:
                messages.error(request, f'Error generating timetable: {str(e)}')

    return render(request, 'timetable/generate.html', {
        'batches': batches,
        'selected_batch': selected_batch,
        'selected_batch_id': selected_batch_id,
        'missing_mappings': missing_mappings,
    })


@login_required
@role_required(['admin', 'coordinator'])
def generate_all_timetables(request):
    """Generate timetables for all batches that have faculty-subject mappings."""
    if request.method != 'POST':
        return redirect('generate_timetable')

    all_batches = Batch.objects.select_related('department').all()
    rooms = list(Room.objects.filter(is_allocatable=True))
    success_count = 0
    fail_count = 0
    skipped_count = 0
    errors = []

    for batch in all_batches:
        faculty_subjects = list(FacultySubject.objects.filter(batch=batch).select_related('faculty', 'subject', 'batch'))
        if not faculty_subjects:
            skipped_count += 1
            continue

        try:
            with transaction.atomic():
                fixed_entries = list(TimetableEntry.objects.filter(is_fixed=True, batch=batch).select_related('batch', 'subject', 'faculty', 'room'))
                combined_classes = list(CombinedClass.objects.filter(batches=batch).prefetch_related('batches').select_related('subject', 'faculty', 'room'))

                solver = TimetableSolver(
                        [batch], None, faculty_subjects, rooms, fixed_entries, combined_classes,
                        working_hours=(
                            batch.shift.start_time if batch.shift else 10,
                            batch.shift.end_time if batch.shift else 18
                        ),
                        lunch_start=batch.shift.lunch_start if batch.shift else 13,
                        lunch_duration=batch.shift.lunch_duration if batch.shift else 1
                    )

                # Block if combined class room capacity insufficient
                if solver.combined_room_warnings:
                    fail_count += 1
                    errors.append(f'{batch}: ' + '; '.join(solver.combined_room_warnings))
                    continue

                success, message = solver.solve()

                if success:
                    # Snapshot existing
                    existing_entries = list(TimetableEntry.objects.filter(batch=batch).select_related('subject', 'faculty', 'room', 'combined_class').prefetch_related('combined_class__batches'))
                    if existing_entries:
                        snapshot = SavedTimetable.objects.create(
                            batch=batch,
                            saved_by=request.user,
                            label=f"{batch} – saved before regeneration on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                        SavedTimetableEntry.objects.bulk_create([
                            SavedTimetableEntry(
                                saved_timetable=snapshot,
                                subject_code=e.subject.code,
                                subject_name=e.subject.name,
                                faculty_name=e.faculty.name,
                                room_number=e.room.room_number,
                                day_of_week=e.day_of_week,
                                start_time=e.start_time,
                                end_time=e.end_time,
                                is_fixed=e.is_fixed,
                                is_combined=bool(e.combined_class_id),
                                combined_batch_sections=', '.join(b.section for b in e.combined_class.batches.all()) if e.combined_class_id else ''
                            ) for e in existing_entries
                        ])

                    TimetableEntry.objects.filter(is_fixed=False, batch=batch, combined_class__isnull=True).delete()
                    for entry_data in solver.solution:
                        TimetableEntry.objects.create(
                            batch_id=entry_data['batch_id'],
                            subject_id=entry_data['subject_id'],
                            faculty_id=entry_data['faculty_id'],
                            room_id=entry_data['room_id'],
                            day_of_week=entry_data['day_of_week'],
                            start_time=entry_data['start_time'],
                            end_time=entry_data['end_time'],
                            is_fixed=False
                        )
                    TimetableEntry.objects.filter(batch=batch, combined_class__isnull=False).delete()
                    for cc in combined_classes:
                        TimetableEntry.objects.create(
                            batch=batch, subject=cc.subject, faculty=cc.faculty, room=cc.room,
                            day_of_week=cc.day_of_week, start_time=cc.start_time, end_time=cc.end_time,
                            is_fixed=True, combined_class=cc
                        )
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f'{batch}: {message}')
        except Exception as e:
            fail_count += 1
            errors.append(f'{batch}: {str(e)}')

    if success_count:
        messages.success(request, f'Generated timetables for {success_count} batch(es) successfully.')
    if skipped_count:
        messages.warning(request, f'Skipped {skipped_count} batch(es) with no faculty-subject mappings.')
    if fail_count:
        error_detail = '\n'.join(f'• {e}' for e in errors)
        messages.error(request, f'Failed for {fail_count} batch(es):\n{error_detail}')

    return redirect('generate_timetable')


@login_required
def timetable_view(request):
    batch_id = request.GET.get('batch')
    # Class advisor: restrict to their batch only
    if request.user.role == 'class_advisor':
        try:
            advisor_batch = request.user.class_advisor_profile.batch
            batches = Batch.objects.filter(pk=advisor_batch.pk).select_related('department')
            if not batch_id:
                batch_id = str(advisor_batch.pk)
        except Exception:
            batches = Batch.objects.none()
    else:
        batches = Batch.objects.select_related('department').all()
    timetable_grid = {}
    editable_entry_ids = set()  # Authorized existing entries only.
    spanned_cells = {}
    combined_grid = {}
    combined_spanned = {}
    selected_batch_obj = Batch.objects.select_related('shift').filter(pk=batch_id).first() if batch_id else None

    if batch_id:
        entries = TimetableEntry.objects.filter(batch_id=batch_id).select_related(
            'subject', 'faculty', 'room', 'combined_class'
        ).prefetch_related('combined_class__batches').order_by('day_of_week', 'start_time')
        from .manual_schedule import can_manage_entry
        for entry in entries:
            if can_manage_entry(request.user, entry):
                editable_entry_ids.add(entry.pk)
            day = entry.day_of_week
            if day not in timetable_grid:
                timetable_grid[day] = {}
            timetable_grid[day][entry.start_time] = entry
            duration = entry.end_time - entry.start_time
            if duration > 1:
                if day not in spanned_cells:
                    spanned_cells[day] = set()
                for offset in range(1, duration):
                    spanned_cells[day].add(entry.start_time + offset)

        # Load combined classes that include this batch
        combined = CombinedClass.objects.filter(batches__id=batch_id).prefetch_related('batches').select_related('subject', 'faculty', 'room')
        for cc in combined:
            day = cc.day_of_week
            if day not in combined_grid:
                combined_grid[day] = {}
            combined_grid[day][cc.start_time] = cc
            duration = cc.end_time - cc.start_time
            if duration > 1:
                if day not in combined_spanned:
                    combined_spanned[day] = set()
                for offset in range(1, duration):
                    combined_spanned[day].add(cc.start_time + offset)

    spanned_cells = {day: list(times) for day, times in spanned_cells.items()}
    combined_spanned = {day: list(times) for day, times in combined_spanned.items()}

    context = {
        'batches': batches,
        'selected_batch': batch_id,
        'timetable_grid': timetable_grid,
        'editable_entry_ids': editable_entry_ids,
        'spanned_cells': spanned_cells,
        'combined_grid': combined_grid,
        'combined_spanned': combined_spanned,
        'days': TimetableEntry.DAYS_OF_WEEK,
        'timeslots': range(
            selected_batch_obj.shift.start_time if selected_batch_obj and selected_batch_obj.shift else 10,
            selected_batch_obj.shift.end_time if selected_batch_obj and selected_batch_obj.shift else 18
        ),
    }
    return render(request, 'timetable/timetable_view.html', context)


@login_required
def manual_entry_create(request):
    from .manual_schedule import manual_entry_create as impl
    return impl(request)
@login_required
def combined_class_list(request):
    combined_classes = CombinedClass.objects.prefetch_related('batches').select_related('subject', 'faculty', 'room').all()
    return render(request, 'timetable/combined_class_list.html', {'combined_classes': combined_classes})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def combined_class_create(request):
    batch_qs = Batch.objects.select_related('department').all()

    if request.method == 'POST':
        form = CombinedClassForm(request.POST, batch_queryset=batch_qs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Combined class created successfully.')
            return redirect('combined_class_list')
    else:
        form = CombinedClassForm(batch_queryset=batch_qs)
    return render(request, 'timetable/combined_class_form.html', {'form': form, 'title': 'Create Combined Class'})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def combined_class_edit(request, pk):
    cc = get_object_or_404(CombinedClass, pk=pk)
    batch_qs = Batch.objects.select_related('department').all()

    if request.method == 'POST':
        form = CombinedClassForm(request.POST, instance=cc, batch_queryset=batch_qs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Combined class updated successfully.')
            return redirect('combined_class_list')
    else:
        form = CombinedClassForm(instance=cc, batch_queryset=batch_qs)
    return render(request, 'timetable/combined_class_form.html', {'form': form, 'title': 'Edit Combined Class'})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def combined_class_delete(request, pk):
    cc = get_object_or_404(CombinedClass, pk=pk)
    if request.method == 'POST':
        cc.delete()
        messages.success(request, 'Combined class deleted successfully.')
        return redirect('combined_class_list')
    return render(request, 'confirm_delete.html', {'object': cc, 'type': 'Combined Class'})


@login_required
def saved_timetable_list(request):
    saved = SavedTimetable.objects.select_related('batch__department', 'saved_by').all()
    return render(request, 'timetable/saved_timetable_list.html', {'saved_timetables': saved})


@login_required
def saved_timetable_view(request, pk):
    snapshot = get_object_or_404(SavedTimetable.objects.select_related('batch__department', 'saved_by'), pk=pk)
    entries = snapshot.entries.all()

    # Build grid: {day: {start_time: entry}}, spanned: {day: [times]}
    grid = {}
    spanned = {}
    for e in entries:
        grid.setdefault(e.day_of_week, {})[e.start_time] = e
        duration = e.end_time - e.start_time
        if duration > 1:
            spanned.setdefault(e.day_of_week, set())
            for offset in range(1, duration):
                spanned[e.day_of_week].add(e.start_time + offset)
    spanned = {day: list(times) for day, times in spanned.items()}

    context = {
        'snapshot': snapshot,
        'grid': grid,
        'spanned': spanned,
        'days': TimetableEntry.DAYS_OF_WEEK,
        'timeslots': range(10, 18),
    }
    return render(request, 'timetable/saved_timetable_view.html', context)


@login_required
@role_required(['admin', 'coordinator'])
def saved_timetable_delete(request, pk):
    snapshot = get_object_or_404(SavedTimetable, pk=pk)
    if request.method == 'POST':
        snapshot.delete()
        messages.success(request, 'Saved timetable deleted.')
        return redirect('saved_timetable_list')
    return render(request, 'confirm_delete.html', {'object': snapshot, 'type': 'Saved Timetable'})


# ── Class Advisor Management ──────────────────────────────────────────────────

@login_required
@role_required(['admin'])
def class_advisor_list(request):
    advisors = ClassAdvisor.objects.select_related('user', 'faculty', 'batch__department').all()
    return render(request, 'advisor/class_advisor_list.html', {'advisors': advisors})


@login_required
@role_required(['admin'])
def class_advisor_create(request):
    faculties = Faculty.objects.select_related('department').all()
    batches = Batch.objects.select_related('department').all()
    # Exclude already-assigned faculties and batches
    assigned_faculty_ids = ClassAdvisor.objects.values_list('faculty_id', flat=True)
    assigned_batch_ids = ClassAdvisor.objects.values_list('batch_id', flat=True)
    faculties = faculties.exclude(id__in=assigned_faculty_ids)
    batches = batches.exclude(id__in=assigned_batch_ids)

    if request.method == 'POST':
        faculty_id = request.POST.get('faculty')
        batch_id = request.POST.get('batch')
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        errors = []
        if not faculty_id:
            errors.append('Faculty is required.')
        if not batch_id:
            errors.append('Batch is required.')
        if not username:
            errors.append('Username is required.')
        if not password:
            errors.append('Password is required.')
        if username and User.objects.filter(username=username).exists():
            errors.append(f'Username "{username}" is already taken.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            faculty = get_object_or_404(Faculty, pk=faculty_id)
            batch = get_object_or_404(Batch, pk=batch_id)
            user = User.objects.create_user(
                username=username,
                password=password,
                role='class_advisor',
                first_name=faculty.name.split()[0],
                last_name=' '.join(faculty.name.split()[1:]),
            )
            ClassAdvisor.objects.create(user=user, faculty=faculty, batch=batch)
            messages.success(request, f'Class Advisor account created. Login: {username} / {password}')
            return redirect('class_advisor_list')

    return render(request, 'advisor/class_advisor_form.html', {
        'faculties': faculties,
        'batches': batches,
        'title': 'Create Class Advisor',
    })


@login_required
@role_required(['admin'])
def class_advisor_reset_password(request, pk):
    advisor = get_object_or_404(ClassAdvisor, pk=pk)
    if request.method == 'POST':
        new_password = request.POST.get('password', '').strip()
        if not new_password:
            messages.error(request, 'Password cannot be empty.')
        else:
            advisor.user.set_password(new_password)
            advisor.user.save()
            messages.success(request, f'Password reset for {advisor.user.username}.')
            return redirect('class_advisor_list')
    return render(request, 'advisor/reset_password.html', {'advisor': advisor})


@login_required
@role_required(['admin'])
def class_advisor_delete(request, pk):
    advisor = get_object_or_404(ClassAdvisor, pk=pk)
    if request.method == 'POST':
        user = advisor.user
        advisor.delete()
        user.delete()
        messages.success(request, 'Class Advisor and their login account deleted.')
        return redirect('class_advisor_list')
    return render(request, 'confirm_delete.html', {'object': advisor, 'type': 'Class Advisor'})


# ── Student Management ────────────────────────────────────────────────────

def _get_advisor_batch(user):
    """Return the batch assigned to a class advisor, or None."""
    try:
        return user.class_advisor_profile.batch
    except Exception:
        return None


@login_required
@role_required(['admin', 'class_advisor'])
def student_list(request):
    if request.user.role == 'class_advisor':
        batch = _get_advisor_batch(request.user)
        if not batch:
            messages.error(request, 'No batch assigned to your profile.')
            return redirect('dashboard')
        students = Student.objects.filter(batch=batch).select_related('user', 'batch__department')
        context_batch = batch
    else:
        batch_id = request.GET.get('batch')
        students = Student.objects.select_related('user', 'batch__department').all()
        if batch_id:
            students = students.filter(batch_id=batch_id)
        context_batch = None

    return render(request, 'students/student_list.html', {
        'students': students,
        'batches': Batch.objects.select_related('department').all() if request.user.role == 'admin' else None,
        'selected_batch_id': request.GET.get('batch', ''),
        'context_batch': context_batch,
    })


@login_required
@role_required(['admin', 'class_advisor'])
def student_create(request):
    if request.user.role == 'class_advisor':
        batch = _get_advisor_batch(request.user)
        if not batch:
            messages.error(request, 'No batch assigned to your profile.')
            return redirect('dashboard')
    else:
        batch = None

    batches = Batch.objects.select_related('department').all() if not batch else None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        roll_number = request.POST.get('roll_number', '').strip()
        batch_id = request.POST.get('batch') if not batch else batch.pk

        errors = []
        if not username: errors.append('Username is required.')
        if not password: errors.append('Password is required.')
        if not batch_id: errors.append('Batch is required.')
        if username and User.objects.filter(username=username).exists():
            errors.append(f'Username "{username}" already exists.')

        if errors:
            for e in errors: messages.error(request, e)
        else:
            selected_batch = batch or get_object_or_404(Batch, pk=batch_id)
            parts = full_name.split(' ', 1)
            user = User.objects.create_user(
                username=username, password=password, role='student',
                first_name=parts[0], last_name=parts[1] if len(parts) > 1 else ''
            )
            Student.objects.create(user=user, batch=selected_batch, roll_number=roll_number)
            messages.success(request, f'Student account created: {username}')
            return redirect('student_list')

    return render(request, 'students/student_form.html', {
        'title': 'Add Student',
        'batches': batches,
        'fixed_batch': batch,
    })


@login_required
@role_required(['admin', 'class_advisor'])
def student_upload_csv(request):
    if request.user.role == 'class_advisor':
        batch = _get_advisor_batch(request.user)
        if not batch:
            messages.error(request, 'No batch assigned to your profile.')
            return redirect('dashboard')
    else:
        batch = None

    batches = Batch.objects.select_related('department').all() if not batch else None

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        batch_id = request.POST.get('batch') if not batch else batch.pk

        if not csv_file:
            messages.error(request, 'Please upload a CSV file.')
        elif not batch_id:
            messages.error(request, 'Please select a batch.')
        else:
            selected_batch = batch or get_object_or_404(Batch, pk=batch_id)
            try:
                decoded = csv_file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(decoded))
                created, skipped, errors = 0, 0, []
                for idx, row in enumerate(reader, start=2):
                    username = row.get('username', '').strip()
                    password = row.get('password', '').strip()
                    full_name = row.get('full_name', '').strip()
                    roll_number = row.get('roll_number', '').strip()
                    if not username or not password:
                        errors.append(f'Row {idx}: username and password are required.')
                        continue
                    if User.objects.filter(username=username).exists():
                        skipped += 1
                        continue
                    parts = full_name.split(' ', 1)
                    user = User.objects.create_user(
                        username=username, password=password, role='student',
                        first_name=parts[0], last_name=parts[1] if len(parts) > 1 else ''
                    )
                    Student.objects.create(user=user, batch=selected_batch, roll_number=roll_number)
                    created += 1
                if errors:
                    messages.warning(request, f'Created {created}, skipped {skipped}. Errors: {"; ".join(errors[:5])}')
                else:
                    messages.success(request, f'Created {created} student accounts. Skipped {skipped} duplicates.')
                return redirect('student_list')
            except Exception as e:
                messages.error(request, f'Error processing CSV: {e}')

    return render(request, 'students/student_csv_upload.html', {
        'title': 'Upload Students CSV',
        'batches': batches,
        'fixed_batch': batch,
    })


@login_required
@role_required(['admin', 'class_advisor'])
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    # Class advisor can only delete students from their batch
    if request.user.role == 'class_advisor':
        batch = _get_advisor_batch(request.user)
        if student.batch != batch:
            messages.error(request, 'You can only manage students in your assigned batch.')
            return redirect('student_list')
    if request.method == 'POST':
        user = student.user
        student.delete()
        user.delete()
        messages.success(request, 'Student account deleted.')
        return redirect('student_list')
    return render(request, 'confirm_delete.html', {'object': student, 'type': 'Student'})


# ── Shift Management ────────────────────────────────────────────────────

@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def shift_list(request):
    shifts = Shift.objects.all()
    return render(request, 'academic/shift_list.html', {'shifts': shifts})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def shift_create(request):
    if request.method == 'POST':
        form = ShiftForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift created successfully.')
            return redirect('shift_list')
    else:
        form = ShiftForm()
    return render(request, 'academic/shift_form.html', {'form': form, 'title': 'Create Shift'})


@login_required
@role_required(['admin', 'coordinator', 'class_advisor'])
def shift_edit(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == 'POST':
        form = ShiftForm(request.POST, instance=shift)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift updated successfully.')
            return redirect('shift_list')
    else:
        form = ShiftForm(instance=shift)
    return render(request, 'academic/shift_form.html', {'form': form, 'title': 'Edit Shift'})


@login_required
@role_required(['admin'])
def shift_delete(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == 'POST':
        shift.delete()
        messages.success(request, 'Shift deleted.')
        return redirect('shift_list')
    return render(request, 'confirm_delete.html', {'object': shift, 'type': 'Shift'})


@login_required
def student_timetable(request):
    """Student's personal timetable view — auto-loads their batch."""
    if request.user.role != 'student':
        return redirect('timetable_view')
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'No batch assigned to your account. Contact your class advisor.')
        return render(request, 'students/student_timetable.html', {'error': True})

    batch = student.batch
    entries = TimetableEntry.objects.filter(batch=batch).select_related(
        'subject', 'faculty', 'room', 'combined_class'
    ).prefetch_related('combined_class__batches').order_by('day_of_week', 'start_time')

    timetable_grid, spanned_cells = {}, {}
    for entry in entries:
        day = entry.day_of_week
        timetable_grid.setdefault(day, {})[entry.start_time] = entry
        duration = entry.end_time - entry.start_time
        if duration > 1:
            spanned_cells.setdefault(day, set())
            for offset in range(1, duration):
                spanned_cells[day].add(entry.start_time + offset)

    spanned_cells = {day: list(times) for day, times in spanned_cells.items()}

    return render(request, 'students/student_timetable.html', {
        'batch': batch,
        'student': student,
        'timetable_grid': timetable_grid,
        'spanned_cells': spanned_cells,
        'days': TimetableEntry.DAYS_OF_WEEK,
        'timeslots': range(10, 18),
    })
