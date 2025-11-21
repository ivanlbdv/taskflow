import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
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
    tasks = Task.objects.filter(
        user=request.user
    ).select_related().prefetch_related()
    overdue_tasks = tasks.filter(
        Q(status='overdue') | Q(due_date__lt=now)
    ).order_by('-priority', 'due_date')
    todo_tasks = tasks.filter(
        status='todo',
        due_date__gte=now
    ).order_by('-priority', 'due_date')
    in_progress_tasks = tasks.filter(
        status='in_progress'
    ).order_by('-priority', 'due_date')
    done_tasks = tasks.filter(
        status='done'
    ).order_by('-due_date')
    context = {
        'overdue_tasks': overdue_tasks,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'done_tasks': done_tasks,
        'total_tasks': Task.objects.filter(user=request.user).count(),
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
            return JsonResponse(
                {'success': False, 'error': 'Неверный статус'},
                status=400
            )
        task.status = new_status
        task.save()
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('dashboard')
        })
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': 'Неверный формат данных'},
            status=400
        )
