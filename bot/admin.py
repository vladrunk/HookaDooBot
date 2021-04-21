from django.contrib import admin
from .models import *


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['uid', 'fname', 'lname', 'username', ]
    search_fields = ['uid', 'fname', 'lname', 'username', ]


@admin.register(Tobacco)
class TobaccoAdmin(admin.ModelAdmin):
    list_display = ['title', 'weight', ]
    list_filter = ['weight', ]
    search_fields = ['title', ]


@admin.register(TobaccoOnSite)
class TobaccoOnSiteAdmin(admin.ModelAdmin):
    list_display = ['site', 'title', 'title_on_site', ]
    search_fields = ['site__title', 'title__title', 'title_on_site', ]


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['title', 'url', 'find_url', ]
    search_fields = ['title', ]


@admin.register(Search)
class SearchAdmin(admin.ModelAdmin):
    list_display = ['search_id', 'user', 'step', 'short_result', ]
    list_filter = ['user', 'step', ]
    search_fields = ['search_id', 'user__uid']
