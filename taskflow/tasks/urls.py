from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tasks/', views.tasks_list, name='tasks_list'),
    path('task/create/', views.task_create, name='task_create'),
    path('task/<int:pk>/update/', views.task_update, name='task_update'),
    path('task/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('task/<int:pk>/update-status/', views.update_task_status, name='update_task_status'),
    path('analytics/', views.analytics, name='analytics'),
    path('logout/', views.user_logout, name='logout'),
]
