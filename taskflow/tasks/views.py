import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import TaskForm
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
            print("Форма не валидна:", form.errors)
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
        # Получаем новую дату из формы
        new_due_date = form.cleaned_data['due_date']

        # Если задача была просрочена, но новая дата в будущем — восстанавливаем исходный статус
        if (task.status == 'overdue'
                and task.original_status  # есть сохранённый исходный статус
                and new_due_date >= timezone.now()):
            task.status = task.original_status
            task.original_status = None  # очищаем после восстановления

        form.save()  # сохраняет task.status и другие поля
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

        # Проверка валидности статуса
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

    status_labels = {
        'overdue': 'Просроченные',
        'todo': 'К выполнению',
        'in_progress': 'В работе',
        'done': 'Выполненные',
        None: 'Все задачи'
    }

    current_label = status_labels.get(status, 'Все задачи')

    context = {
        'tasks': tasks,
        'current_status': status,
        'current_label': current_label,
        'total_count': tasks.count(),
    }
    return render(request, 'tasks/tasks_list.html', context)
