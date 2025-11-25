from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AdminSplitDateTime
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import Task


class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = '__all__'
        widgets = {
            'due_date': AdminSplitDateTime(),
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 41})
        }


class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm

    list_display = (
        'title',
        'user',
        'due_date',
        'status',
        'priority',
        'created_at',
        'updated_at'
    )

    list_filter = (
        'status',
        'priority',
        'user',
        'created_at',
        'updated_at'
    )

    search_fields = ('title', 'description')
    date_hierarchy = 'due_date'
    ordering = ('-due_date',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': (
                'title',
                'description',
                'due_date',
                'status',
                'priority',
                'user'
            )
        }),
        (_('Временные метки'), {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'user' in form.base_fields:
            form.base_fields['user'].queryset = User.objects.all().order_by(
                'username'
            )
        return form


admin.site.register(Task, TaskAdmin)


class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    filter_horizontal = ()


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.site_header = _('Панель управления задачами')
admin.site.site_title = _('Административная панель')
admin.site.index_title = _('Управление задачами')
