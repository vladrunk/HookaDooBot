from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .services.cfg import BOT_TOKEN
from .views import BotUpdate, robots_txt

urlpatterns = [
    path(f'robots.txt', robots_txt),
    path(f'webhook/{BOT_TOKEN}', csrf_exempt(BotUpdate.as_view()), name='update'),
]
