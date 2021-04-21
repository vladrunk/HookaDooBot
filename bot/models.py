from django.db import models
from django.template.defaultfilters import truncatechars


class User(models.Model):
    uid = models.CharField(
        default='',
        verbose_name='User ID',
        max_length=255,
    )
    fname = models.CharField(
        default='',
        verbose_name='Имя',
        max_length=255,
    )
    lname = models.CharField(
        default='',
        verbose_name='Фамилия',
        max_length=255,
        blank=True,
        null=True,
    )
    username = models.CharField(
        default='',
        verbose_name='Ник',
        max_length=255,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f'{self.uid} {self.fname}'

    class Meta:
        verbose_name = 'Юзер'
        verbose_name_plural = 'Юзеры'


class Tobacco(models.Model):
    title = models.CharField(
        default='',
        verbose_name='Наименование',
        max_length=255,
    )

    weight = models.CharField(
        default=0,
        verbose_name='Вес',
        max_length=255,
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Табак'
        verbose_name_plural = 'Табаки'


class TobaccoOnSite(models.Model):
    title = models.ForeignKey(
        to='Tobacco',
        related_name='tobacco_title',
        default='',
        verbose_name='Общее наименование',
        on_delete=models.SET_DEFAULT,
        null=True,
    )
    site = models.ForeignKey(
        to='Site',
        related_name='site_fk',
        default='',
        verbose_name='Сайт',
        on_delete=models.SET_DEFAULT,
        null=True,
    )
    title_on_site = models.CharField(
        default='',
        verbose_name='Наименование на сайте',
        max_length=255,
    )

    def __str__(self):
        return f'{self.title} {self.site}'

    class Meta:
        verbose_name = 'Табак на сайтах'
        verbose_name_plural = 'Табаки на сайтах'


class Site(models.Model):
    title = models.CharField(
        default='',
        verbose_name='Наименование',
        max_length=255,
    )
    url = models.URLField(
        default='',
        verbose_name='Ссылка',
        max_length=255,
    )
    find_url = models.URLField(
        default='',
        verbose_name='Поиск',
        max_length=255,
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Сайт'
        verbose_name_plural = 'Сайты'


class Search(models.Model):
    search_id = models.CharField(
        default='',
        verbose_name='Id запроса',
        max_length=255,
        editable=False,
        null=False,
        blank=False,
    )
    user = models.ForeignKey(
        to='User',
        related_name='user_search',
        default='',
        verbose_name='Юзер',
        on_delete=models.SET_DEFAULT,
        null=True,
    )
    product = models.CharField(
        default='',
        verbose_name='Продукт',
        max_length=255,
        choices=[('tabak', 'Табак'),
                 ('charcoal', 'Уголь')],
    )
    company = models.ForeignKey(
        to='Tobacco',
        related_name='tobacco_search',
        default='',
        verbose_name='Фирма',
        on_delete=models.SET_DEFAULT,
        null=True,
    )
    extra = models.CharField(
        default='',
        verbose_name='Экстра',
        max_length=255,
        blank=True,
    )
    flavor = models.CharField(
        default='',
        verbose_name='Вкус',
        max_length=255,
        blank=True,
    )
    step = models.CharField(
        default='',
        verbose_name='Шаг',
        max_length=255,
        choices=[('product', 'Продукт',),
                 ('company', 'Фирма'),
                 ('extra', 'Экстра'),
                 ('flavor', 'Вкус'),
                 ('agree_search', 'Подтверждение'),
                 ('result', 'Результат')]
    )
    result = models.TextField(
        default='',
        verbose_name='Результат',
        null=True,
        blank=True,
    )

    def __str__(self):
        return f'{self.user} {self.step}'

    def short_result(self):
        return truncatechars(self.result, 35)

    class Meta:
        verbose_name = 'Поиск'
        verbose_name_plural = 'Поиски'
