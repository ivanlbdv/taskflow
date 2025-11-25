import datetime
import io
import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import RegistrationForm, TaskForm
from .models import Task


@login_required
def dashboard(request):
    now = timezone.now()

    Task.objects.filter(
        user=request.user,
        due_date__lt=now,
        status__in=['todo', 'in_progress'],
        original_status__isnull=True
    ).update(
        status='overdue',
        original_status=models.F('status')
    )

    tasks = Task.objects.filter(user=request.user)
    overdue_tasks = tasks.filter(status='overdue').order_by('due_date', '-priority')
    todo_tasks = tasks.filter(status='todo').order_by('due_date', '-priority')
    in_progress_tasks = tasks.filter(status='in_progress').order_by('due_date', '-priority')
    done_tasks = tasks.filter(status='done').order_by('due_date', '-priority')

    context = {
        'overdue_tasks': overdue_tasks,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'done_tasks': done_tasks,
        'total_tasks': tasks.count(),
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.delete()
    return redirect('dashboard')


@login_required
def analytics(request):
    tasks = Task.objects.filter(user=request.user)
    status_counts = {}
    for status, _ in Task.STATUS_CHOICES:
        status_counts[status] = tasks.filter(status=status).count()
    priority_counts = {}
    for priority, _ in Task.PRIORITY_CHOICES:
        priority_counts[priority] = tasks.filter(priority=priority).count()
    overdue_count = tasks.filter(
        status='overdue'
    ).count()
    context = {
        'status_counts': status_counts,
        'priority_counts': priority_counts,
        'overdue_count': overdue_count,
        'total_tasks': tasks.count(),
    }
    return render(request, 'tasks/analytics.html', context)


@login_required
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            return redirect('dashboard')
    else:
        form = TaskForm()
    context = {'form': form}
    return render(request, 'tasks/task_form.html', context)


def user_logout(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect('dashboard')


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    form = TaskForm(request.POST or None, instance=task)

    if request.method == 'POST' and form.is_valid():
        new_due_date = form.cleaned_data['due_date']

        if (task.status == 'overdue'
                and task.original_status
                and new_due_date >= timezone.now()):
            task.status = task.original_status
            task.original_status = None

        form.save()

        return redirect('dashboard')

    context = {'form': form, 'task': task}
    return render(request, 'tasks/task_form.html', context)


@login_required
@require_POST
def update_task_status(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')

        if new_status not in dict(Task.STATUS_CHOICES):
            return JsonResponse({
                'success': False,
                'error': 'Нельзя изменить статус: задача просрочена. Обновите срок выполнения.'
            }, status=400)

        if new_status not in dict(Task.STATUS_CHOICES):
            return JsonResponse({
                'success': False,
                'error': 'Неверный статус'
            }, status=400)

        task.status = new_status
        task.save()

        return JsonResponse({
            'success': True,
            'redirect_url': reverse('dashboard')
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат данных'
        }, status=400)


@login_required
def tasks_list(request):
    status = request.GET.get('status', None)
    sort_by = request.GET.get('sort', 'id')
    tasks = Task.objects.filter(user=request.user)

    if status == 'overdue':
        tasks = tasks.filter(
            models.Q(status='overdue') |
            models.Q(due_date__lt=timezone.now(), status__in=['todo', 'in_progress'])
        )
    elif status == 'todo':
        tasks = tasks.filter(status='todo')
    elif status == 'in_progress':
        tasks = tasks.filter(status='in_progress')
    elif status == 'done':
        tasks = tasks.filter(status='done')

    tasks = tasks.order_by('due_date')

    sort_mapping = {
        'id': 'id',
        '-id': '-id',
        'title': 'title',
        '-title': '-title',
        'status': 'status',
        '-status': '-status',
        'priority': 'priority',
        '-priority': '-priority',
        'due_date': 'due_date',
        '-due_date': '-due_date',
    }
    order_field = sort_mapping.get(sort_by, 'id')
    tasks = tasks.order_by(order_field)

    status_labels = {
        'overdue': 'Просроченные',
        'todo': 'К выполнению',
        'in_progress': 'В работе',
        'done': 'Выполненные',
        None: 'Все задачи'
    }

    current_label = status_labels.get(status, 'Все задачи')

    paginator = Paginator(tasks, 10)
    page_number = request.GET.get('page')
    tasks_page = paginator.get_page(page_number)

    context = {
        'tasks': tasks_page,
        'current_status': status,
        'current_label': current_label,
        'total_count': tasks.count(),
        'sort_by': sort_by,
    }
    return render(request, 'tasks/tasks_list.html', context)


def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    return render(request, 'tasks/task_detail.html', {'task': task})


@login_required
@require_GET
def tasks_stats_api(request):
    period = request.GET.get('period', 'month')
    user = request.user

    now = timezone.now()
    if period == 'day':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_date = (now - datetime.timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = None

    tasks = Task.objects.filter(user=user)
    if start_date:
        tasks = tasks.filter(created_at__gte=start_date)

    status_counts = {}
    for status, _ in Task.STATUS_CHOICES:
        status_counts[status] = tasks.filter(status=status).count()

    return JsonResponse({
        'overdue': status_counts.get('overdue', 0),
        'todo': status_counts.get('todo', 0),
        'in_progress': status_counts.get('in_progress', 0),
        'done': status_counts.get('done', 0)
    })


@login_required
def export_tasks(request):
    status = request.GET.get('status', None)
    sort_by = request.GET.get('sort', 'id')
    tasks = Task.objects.filter(user=request.user)

    status_labels = {
        'overdue': 'Просроченные',
        'todo': 'К выполнению',
        'in_progress': 'В работе',
        'done': 'Выполненные',
        None: 'Все задачи'
    }
    current_label = status_labels.get(status, 'Все задачи')

    if status == 'overdue':
        tasks = tasks.filter(
            models.Q(status='overdue') |
            models.Q(
                due_date__lt=timezone.now(),
                status__in=['todo', 'in_progress']
            )
        )
    elif status:
        tasks = tasks.filter(status=status)

    sort_mapping = {
        'id': 'id',
        '-id': '-id',
        'title': 'title',
        '-title': '-title',
        'status': 'status',
        '-status': '-status',
        'priority': 'priority',
        '-priority': '-priority',
        'due_date': 'due_date',
        '-due_date': '-due_date',
    }
    order_field = sort_mapping.get(sort_by, 'id')
    tasks = tasks.order_by(order_field)

    try:
        output = io.StringIO()
        output.write(f"Экспорт задач (статус: {current_label})\n")
        output.write("=" * 50 + "\n\n")

        for task in tasks:
            output.write(f"Задача: {task.title}\n")
            output.write(f"Описание: {task.description}\n")
            output.write(f"Срок: {task.due_date}\n")
            output.write(f"Приоритет: {task.get_priority_display()}\n")
            output.write(f"Статус: {task.get_status_display()}\n")
            output.write(f"Пользователь: {task.user.username}\n")
            output.write("-" * 50 + "\n")

        filename = f"export_tasks_{status or 'all'}.txt"

        response = HttpResponse(
            output.getvalue(),
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return HttpResponse(
            f'Произошла ошибка при экспорте: {str(e)}',
            status=500
        )


def auth_view(request):
    login_form = AuthenticationForm()
    register_form = RegistrationForm()

    if request.method == 'POST':
        if 'login-submit' in request.POST:
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                return redirect('dashboard')
        elif 'register-submit' in request.POST:
            register_form = RegistrationForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                return redirect('dashboard')

    return render(request, 'tasks/auth.html', {
        'login_form': login_form,
        'register_form': register_form
    })
