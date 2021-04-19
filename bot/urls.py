from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .management.commands.parser import start
from .services.cfg import BOT_TOKEN
from .views import BotUpdate, robots_txt

urlpatterns = [
    path("robots.txt", robots_txt),
    path(f'webhook/{BOT_TOKEN}', csrf_exempt(BotUpdate.as_view()), name='update'),
    path(f'parser', start, name='parser'),
]
