import re
from datetime import timedelta

import pymorphy2
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

morph = pymorphy2.MorphAnalyzer()

IMPORTANT_WORDS_WEIGHTS = {
    'отчёт': 10, 'отчет': 10, 'сбой': 10, 'ошибка': 10, 'авария': 10,
    'штраф': 10, 'пени': 10, 'блокировка': 10, 'отключение': 10,
    'взлом': 10, 'угроза': 10, 'риск': 9, 'проблема': 8, 'суд': 10,
    'проверка': 8, 'инспекция': 9, 'расследование': 9,
    'босс': 9, 'руководитель': 9, 'директор': 9, 'начальник': 8,
    'клиент': 9, 'заказчик': 9, 'инвестор': 9, 'партнёр': 8, 'партнер': 8,
    'главбух': 8, 'юрист': 8, 'адвокат': 8, 'врач': 9,
    'договор': 9, 'контракт': 9, 'счёт': 9, 'счет': 9, 'платёж': 9, 'платеж': 9,
    'оплата': 8, 'бюджет': 8, 'финансы': 8, 'налог': 9, 'прибыль': 7,
    'KPI': 8, 'OKR': 8, 'аудит': 8, 'отчётность': 9, 'отчетность': 9, 'квартал': 7, 'годовой': 8,
    'подготовить': 7, 'согласовать': 8, 'утвердить': 8, 'подписать': 8,
    'представить': 7, 'предоставить': 7, 'сдать': 6, 'решить': 7,
    'организовать': 6, 'провести': 6, 'отправить': 5, 'заключить': 7,
    'настроить': 6, 'восстановить': 7, 'исправить': 7,
    'встреча': 6, 'совещание': 6, 'конференция': 6, 'звонок': 5,
    'переговоры': 8, 'планёрка': 5, 'планерка': 5, 'брифинг': 6, 'электронка': 5,
    'письмо': 4, 'сообщение': 4, 'напоминание': 5,
    'проект': 7, 'релиз': 8, 'деплой': 8, 'развёртывание': 8, 'развертывание': 8,
    'тестирование': 6, 'дедлайн': 9, 'крайний срок': 10,
    'сегодня': 5, 'завтра': 5, 'итоговый': 6, 'финальный': 7,
    'здоровье': 9, 'лечение': 8, 'приём': 7, 'прием': 7, 'анализ': 7, 'УЗИ': 7,
    'рентген': 7, 'рецепт': 6, 'температура': 7, 'травма': 9,
    'госпитализация': 10, 'реанимация': 10,
    'семья': 8, 'родители': 7, 'мама': 7, 'папа': 7, 'сын': 9, 'дочь': 9,
    'ребёнок': 9, 'ребенок': 9, 'супруг': 7, 'супруга': 7, 'муж': 7, 'жена': 7,
    'дом': 6, 'квартира': 6, 'аренда': 6, 'коммуналка': 6,
    'свет': 5, 'вода': 5, 'газ': 5, 'квартплата': 7,
    'ипотека': 9, 'наследство': 9, 'ремонт': 6, 'мастер': 5,
    'протечка': 8, 'замок': 5, 'дверь': 5, 'интернет': 5, 'связь': 5,
    'срочно': 8, 'экстренно': 9, 'немедленно': 9, 'важно': 7,
    'критично': 9, 'приоритетно': 7, 'требуется': 6, 'необходимо': 6,
    'нужно': 5, 'обязательно': 6, 'жду': 5, 'ждут': 5, 'давно': 4,
}

IGNORED_WORDS = {
    'почта', 'электронная', 'кофе', 'обед', 'перерыв', 'отдых',
    'прогулка', 'фильм', 'сериал', 'игры', 'музыка', 'отпуск',
    'выходные', 'праздник', 'вечеринка', 'подарок', 'цветы'
}


class Task(models.Model):
    STATUS_CHOICES = [
        ('overdue', 'Просроченные'),
        ('todo', 'К выполнению'),
        ('in_progress', 'В работе'),
        ('done', 'Выполнены'),
    ]
    PRIORITY_CHOICES = [
        ('high', 'Высокий'),
        ('medium', 'Средний'),
        ('low', 'Низкий'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    @staticmethod
    def calculate_priority(due_date, title):
        if not title or not title.strip():
            return 'medium'
        title = title.strip()

        words = re.findall(r'[а-яё]+', title.lower())
        lemmas = set()

        for word in words:
            parsed = morph.parse(word)[0]
            lemma = parsed.normal_form
            lemmas.add(lemma)

        filtered_lemmas = {
            lemma for lemma in lemmas
            if lemma in IMPORTANT_WORDS_WEIGHTS and lemma not in IGNORED_WORDS
        }
        total_weight = sum(
            IMPORTANT_WORDS_WEIGHTS.get(lemma, 0)
            for lemma in filtered_lemmas
        )

        is_urgent = due_date < timezone.now() + timezone.timedelta(days=1)
        is_important = total_weight >= 8

        if is_urgent and is_important:
            return 'high'
        elif is_urgent or is_important:
            return 'medium'
        else:
            return 'low'

    def save(self, *args, **kwargs):
        if not self.pk and not self.priority:
            self.priority = self.calculate_priority(
                self.due_date,
                self.title,
                self.description
            )

        if self.due_date < timezone.now() and self.status != 'overdue':
            self.status = 'overdue'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
