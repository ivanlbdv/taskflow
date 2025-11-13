import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .forms import TaskForm
from .models import Task


@login_required
def dashboard(request):
    tasks = Task.objects.filter(user=request.user).order_by('priority', 'due_date')
    context = {
        'tasks': tasks,
        'Task': Task,
    }
    return render(request, 'tasks/dashboard.html', context)


@method_decorator(login_required, name='dispatch')
class TaskUpdateView(View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk, user=request.user)
        data = json.loads(request.body)

        # Обновление статуса (перетаскивание между колонками)
        if 'status' in data:
            task.status = data['status']

        # Обновление полей при редактировании
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'due_date' in data:
            task.due_date = data['due_date']

        task.save()
        return JsonResponse({'status': 'success'})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.delete()
    return redirect('dashboard')


@login_required
def analytics(request):
    tasks = Task.objects.filter(user=request.user)

    # Статистика по статусам
    status_counts = {}
    for status, _ in Task.STATUS_CHOICES:
        status_counts[status] = tasks.filter(status=status).count()

    # Статистика по приоритетам
    priority_counts = {}
    for priority, _ in Task.PRIORITY_CHOICES:
        priority_counts[priority] = tasks.filter(priority=priority).count()

    # Просроченные задачи
    overdue_count = tasks.filter(
        status='todo',
        due_date__lt=timezone.now()
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
    form = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        return redirect('dashboard')
    context = {'form': form}
    return render(request, 'tasks/task_create.html', context)


def user_logout(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect('dashboard')


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)

    if request.method == 'POST' and request.headers.get('Content-Type') == 'application/json':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')

            if not new_status:
                return JsonResponse({'error': 'Статус не указан'}, status=400)
            if new_status not in [choice[0] for choice in Task.STATUS_CHOICES]:
                return JsonResponse({'error': 'Недопустимый статус'}, status=400)

            task.status = new_status
            task.save()

            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Неверный JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect('dashboard')

        context = {'form': form, 'task': task}
        return render(request, 'tasks/task_form.html', context)

    else:
        form = TaskForm(instance=task)
        context = {'form': form, 'task': task}
        return render(request, 'tasks/task_form.html', context)
