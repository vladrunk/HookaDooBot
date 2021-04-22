from time import sleep
from itertools import zip_longest
from string import ascii_letters, digits
from json import dumps

import logging
from loguru import logger
from telebot import logger as bot_logger
from notifiers.logging import NotificationHandler
from nanoid import generate
from telebot import TeleBot, util
from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update, ForceReply

from django.http import JsonResponse
from django.views import View
from django.http import HttpResponse
from django.views.decorators.http import require_GET

from HookaDooBot.settings import LOG_IS_SET
from .models import User, Search, Tobacco
from .services.cfg import WEBHOOK_URL, BOT_TOKEN, NOTIFY_BOT_TOKEN, NOTIFY_CHAT_ID
from .services.finder import start as finder_start

bot = TeleBot(token=BOT_TOKEN)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


if not LOG_IS_SET:
    handler = NotificationHandler(
        "telegram",
        defaults={
            "token": NOTIFY_BOT_TOKEN,
            "chat_id": NOTIFY_CHAT_ID
        }
    )
    logger.add(handler, level=logging.WARNING)

    bot_logger.setLevel(logging.WARNING)
    bot_logger.removeHandler(bot_logger.handlers[0])
    bot_logger.addHandler(InterceptHandler())

    logger.add('./logs/{time:YYYY-MM-DD_HH-mm-ss}.log',
               encoding='UTF-8',
               backtrace=True,
               diagnose=True,
               rotation='10 MB',
               compression='zip',
               )

    LOG_IS_SET = True


@require_GET
def robots_txt(request):
    lines = [
        "User-Agent: *",
        "Disallow: /",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


class BotUpdate(View):

    @staticmethod
    def get(request):
        logger.warning('Запрос на установку webhook-а.')
        logger.info('Получаем информацию о webhook-е со стороны Telegram.')
        webhook_prev_url = bot.get_webhook_info().url
        webhook_url = WEBHOOK_URL.format(
            domain=request.headers['HOST']
            if not request.headers.get('X-Original-Host') else request.headers['X-Original-Host']
        )
        sleep(1)
        logger.info('Сверяем url нашего webhook-а c url полученным от Telegram.')
        if webhook_url != webhook_prev_url:
            if webhook_prev_url:
                logger.info('Удаляем старый webhook на Telegram')
                bot.remove_webhook()
                sleep(1)
            logger.info('Устанавливаем свой webhook на Telegram.')
            res = bot.set_webhook(
                url=webhook_url,
                max_connections=100,
            )
            if res:
                logger.warning('Webhook установлен.')
                text = 'Webhook установлен. Бот запущен.'
                code = 200
            else:
                logger.warning('Webhook не удалось установить.')
                text = 'Webhook не удалось установить. Ошибка.'
                code = 500
        else:
            logger.warning('Webhook не требует обновления.')
            text = 'Webhook не требует обновления. Бот запущен.'
            code = 200
        return JsonResponse({
            'code': code,
            'message': text,
            'webhook_url': webhook_url
        })

    @staticmethod
    def post(request):
        bot.process_new_updates(
            [
                Update.de_json(
                    request.body.decode('UTF-8')
                )
            ]
        )
        return JsonResponse({'code': 200})


CALLBACKS = {
    'start_search': 'start_search',
    'tabak': 'tabak',
    'charcoal': 'charcoal',
    'extra': 'extra',
    'choose_flavor': 'choose_flavor',
    'agree_search': 'agree_search',
    'result': 'result',
}
SEARCH_ID_TEXT = '`ID поиска: {id}`\n\n'


def json_to_str(obj):
    return dumps(obj, ensure_ascii=False)


def split_long_text(text):
    split_text = util.split_string(text, 3000)
    res = []
    for i, n in enumerate(split_text):
        if not n.endswith('\n'):
            n += split_text[i + 1][:split_text[i + 1].find('\n') + 1]
            split_text[i + 1] = split_text[i + 1][split_text[i + 1].find('\n') + 1:]
        res.append(n)
    return res


def delete_message(m):
    logger.info(f'[{m.chat.id}]|Удаляем сообщение.')
    bot.delete_message(
        chat_id=m.chat.id,
        message_id=m.message_id,
    )


def check_reply_to_message(m):
    if m.reply_to_message:
        res = True if ('ID' in m.reply_to_message.text and
                       m.reply_to_message.from_user.id == 1157687780) else False
    else:
        res = False
    return res


def get_product_title(call):
    data = call.data.split('|')[2]
    row, col = data.split('-')
    return Tobacco.objects.get(
        title=call.message.reply_markup.keyboard[int(row)][int(col)].text
    )


def get_product_extra(call):
    index = int(call.data.split('|')[2])
    extra = call.message.reply_markup.keyboard[index][0].text.split()[0]
    return extra


def btn_start_search():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton('Начать поиск', callback_data=CALLBACKS['start_search']),
    )
    return markup


def btns_choose_product(search):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton('Табак', callback_data=f'{CALLBACKS["tabak"]}|{search.search_id}'),
        InlineKeyboardButton('Уголь', callback_data=f'{CALLBACKS["charcoal"]}|{search.search_id}'),
    )
    return markup


def btns_choose_company(search):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    if search.product == 'tabak':
        products = Tobacco.objects.all().order_by('title')
    elif search.product == 'charcoal':
        products = []
    else:
        products = []
    products_half_left = products[:len(products) // 2]
    products_half_right = products[len(products) // 2:]
    for i, v in enumerate(zip_longest(products_half_left, products_half_right)):
        if v[0] is not None:
            markup.add(
                InlineKeyboardButton(
                    text=f'{v[0].title}',
                    callback_data=f'{CALLBACKS["extra"]}|{search.search_id}|{i}-0'
                ),
                InlineKeyboardButton(
                    text=f'{v[1].title}',
                    callback_data=f'{CALLBACKS["extra"]}|{search.search_id}|{i}-1'
                ),
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    text=f'{v[1].title}',
                    callback_data=f'{CALLBACKS["extra"]}|{search.search_id}|{i}-0'
                ),
            )
    return markup


def btns_choose_extra(search):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if search.product == 'tabak':
        extras = [int(e) for e in search.company.weight.split(',') if e.isdigit()]
    elif search.product == 'charcoal':
        extras = []
    else:
        extras = []
    for i, extra in enumerate(extras):
        markup.add(
            InlineKeyboardButton(
                text=f'{extra}' + (' грамм' if extra > 10 else ' кг'),
                callback_data=f'{CALLBACKS["choose_flavor"]}|{search.search_id}|{i}'
            ),
        )
    return markup


def btn_agree_search(search):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(
            text=f'Поиск',
            callback_data=f'{CALLBACKS["result"]}|{search.search_id}'),
    )
    return markup


@bot.callback_query_handler(func=lambda call: CALLBACKS['start_search'] == call.data.split('|')[0])
def cb_start_search(call):
    logger.info(f'[{call.message.chat.id}]|"Начать поиск". Процесс выбора продукта.')
    search = Search.objects.create(
        search_id=generate(ascii_letters[:] + digits[:], 10),
        user=User.objects.get(uid=call.message.chat.id),
        step='product',
    )
    search.save()
    text = f'{SEARCH_ID_TEXT.format(id=search.search_id)}' \
           f'Какой продукт ищем?'
    logger.info(f'[{call.message.chat.id}]|Отправляем сообщение с выбором продукта.')
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=btns_choose_product(search),
        parse_mode='MarkdownV2',
    )


@bot.callback_query_handler(func=lambda call: CALLBACKS['tabak'] == call.data.split('|')[0])
def cb_tabak(call):
    logger.info(f'[{call.message.chat.id}]|Процесс выбора марки табака.')
    search = Search.objects.get(
        search_id=call.data.split('|')[1],
    )
    search.product = 'tabak'
    search.step = 'company'
    search.save()
    text = f'{SEARCH_ID_TEXT.format(id=search.search_id)}' \
           f'Какой табак желаете найти?'
    logger.info(f'[{call.message.chat.id}]|Отправляем сообщение с выбором марки табака.')
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=btns_choose_company(search),
        parse_mode='MarkdownV2',
    )


@bot.callback_query_handler(func=lambda call: CALLBACKS['charcoal'] == call.data.split('|')[0])
def cb_charcoal(call):
    logger.info(f'[{call.message.chat.id}]|Процесс выбора угля.')
    text = 'Данный функционал еще в разработке'
    logger.info(f'[{call.message.chat.id}]|Отправляем уведомление, что уголь еще в разработке.')
    bot.answer_callback_query(
        callback_query_id=call.id,
        text=text,
        show_alert=True,
    )


@bot.callback_query_handler(func=lambda call: CALLBACKS['extra'] == call.data.split('|')[0])
def cb_extra(call):
    logger.info(f'[{call.message.chat.id}]|Процесс выбора экстры.')
    search = Search.objects.get(
        search_id=call.data.split('|')[1],
    )
    search.company = get_product_title(call)
    search.step = 'extra'
    search.save()
    if search.product == 'tabak':
        text = f'{SEARCH_ID_TEXT.format(id=search.search_id)}' \
               f'Какой вес табака?'
    else:
        text = ''
    logger.info(f'[{call.message.chat.id}]|Отправляем сообщение с выбором экстры.')
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=btns_choose_extra(search),
        parse_mode='MarkdownV2',
    )


@bot.callback_query_handler(func=lambda call: CALLBACKS['choose_flavor'] == call.data.split('|')[0])
def cb_choose_flavor(call):
    logger.info(f'[{call.message.chat.id}]|Процесс выбора вкуса табака.')
    search = Search.objects.get(
        search_id=call.data.split('|')[1],
    )
    search.extra = get_product_extra(call)
    search.step = 'flavor'
    search.save()
    markup_force_reply = ForceReply(selective=False)
    text = f'{SEARCH_ID_TEXT.format(id=search.search_id)}' \
           f'{search.company} {search.extra}\n\n' \
           f'Какой вкус табака найти?\n\n' \
           f'_Чтобы найти все вкусы напиши \- _*все*'
    delete_message(call.message)
    logger.info(f'[{call.message.chat.id}]|Отправляем сообщение с просьбой написать искомый вкус.')
    bot.send_message(
        chat_id=call.message.chat.id,
        text=text,
        parse_mode='MarkdownV2',
        reply_markup=markup_force_reply,
    )


@bot.callback_query_handler(func=lambda call: CALLBACKS['result'] == call.data.split('|')[0])
def cb_result(call):
    logger.info(f'[{call.message.chat.id}]|Процесс старта поиска табака в базе сайтов.')
    text_q = "Производим поиск по базе сайтов."
    logger.info(f'[{call.message.chat.id}]|Отправляем уведомление, что поиск начат.')
    try:
        bot.answer_callback_query(
            callback_query_id=call.id,
            text=text_q,
            cache_time=60,
        )
    except ApiTelegramException as e:
        logger.info(f'[{call.message.chat.id}]|Не удалось отправить уведомлениео начале поиска. Ошибка: {e}')
    finally:
        search = Search.objects.get(
            search_id=call.data.split('|')[1],
        )
    header_text = f'{SEARCH_ID_TEXT.format(id=search.search_id)}' \
                  f'Ваш запрос: {search.company} {search.flavor} {search.extra}\n\n'

    # Тупая заглушка на ошибку в процессе поиска
    # Переделай, когда будет время
    try:
        find_result_text = finder_start(
            company=search.company, flavor=search.flavor, extra=search.extra, uid=call.message.chat.id
        )
        find_error = False
    except Exception as e:
        find_result_text = 'Ошибка'
        find_error = e

    if find_result_text == '':
        find_result_text = '\nПо вашему запросу табака в наличии нет'

    if find_error:
        logger.error(f'[{call.message.chat.id}]|Ошибка во время поиска. Ошибка: {find_error}')
        text = header_text + 'во время поиска произошла ошибка. ' \
                             'Обратитесь, пожалуйста, к ажминистратору @vladrunk с указанием ID поиска.'
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode='Markdown',
            disable_web_page_preview=True,
        )
    else:
        search.result = find_result_text
        search.save()
        if len(find_result_text) > 4500:
            logger.info(f'[{call.message.chat.id}]|Результат поиска длинее 4500 символов. Делим результат на части.')
            text = split_long_text(header_text + find_result_text)
        else:
            text = header_text + find_result_text
        if isinstance(text, str):
            logger.info(f'[{call.message.chat.id}]|Отправляем результат поиска.')
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='Markdown',
                disable_web_page_preview=True,
            )
        else:
            logger.info(f'[{call.message.chat.id}]|Отправляем результат поиска #1.')
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text[0],
                parse_mode='Markdown',
                disable_web_page_preview=True,
            )
            for i, t in enumerate(text):
                if i == 0:
                    continue
                if len(t) > 1:
                    logger.info(f'[{call.message.chat.id}]|Отправляем результат поиска #{i + 1}.')
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=t,
                        parse_mode='Markdown',
                        disable_web_page_preview=True,
                    )

    cmd_start(call.message)


@bot.message_handler(commands=['start'])
def cmd_start(m):
    logger.info(f'[{m.chat.id}]|Получили команду /start.')
    _, is_new = User.objects.get_or_create(
        uid=m.chat.id,
        defaults={
            'fname': m.chat.first_name,
            'lname': m.chat.last_name,
            'username': m.chat.username,
        }
    )

    if is_new:
        logger.warning(f'[{m.chat.id}]|Новый юзер')
        text = f'Добро пожаловать, {m.chat.first_name} \N{grinning face}'
    else:
        logger.info(f'[{m.chat.id}]|Юзер уже есть в БД')
        text = f'{m.chat.first_name}, ещё по табачку ? \N{drooling face}'
    logger.info(f'[{m.chat.id}]|Отправляем ответ на /start.')
    bot.send_message(
        chat_id=m.chat.id,
        text=text,
        reply_markup=btn_start_search(),
    )


@bot.message_handler(func=check_reply_to_message)
def msg_agree_search(m):
    logger.info(f'[{m.chat.id}]|Процесс подтверждения поиска табака.')
    m_edit = m.reply_to_message
    search_id = m_edit.text.splitlines()[0].split(': ')[1]
    search = Search.objects.get(search_id=search_id)
    if search.step != 'flavor':
        delete_message(m)
        return
    search.flavor = m.text
    search.step = 'result'
    search.save()
    text = f'{SEARCH_ID_TEXT.format(id=search.search_id)}' \
           f'Ваш запрос: {search.company} {search.flavor} {search.extra}'
    delete_message(m_edit)
    delete_message(m)
    logger.info(f'[{m.chat.id}]|Отправляем сообщение для подтверждения.')
    bot.send_message(
        chat_id=m_edit.chat.id,
        text=text,
        reply_markup=btn_agree_search(search),
        parse_mode='MarkdownV2',
    )


@bot.message_handler(func=lambda m: True)
def any_msg(m):
    logger.info(f'[{m.chat.id}]|Пришло сообщение которое не обрабатывается ботом.')
    delete_message(m)
