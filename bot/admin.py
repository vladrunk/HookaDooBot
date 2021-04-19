from django.contrib import admin

from django.apps import apps

app_models = apps.get_app_config('bot').get_models()
for model in app_models:
    @admin.register(model)
    class TobaccoOnSiteAdmin(admin.ModelAdmin):
        list_display = [field.name for field in model._meta.fields]
