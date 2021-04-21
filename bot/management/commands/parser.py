from typing import Union
import requests
import re
from bs4 import BeautifulSoup, ResultSet, Tag, NavigableString
from bot.models import Site, Tobacco, TobaccoOnSite
from django.core.management.base import BaseCommand

from loguru import logger


def __get_soup(url: str) -> BeautifulSoup:
    logger.info(f'Переходим по ссылке {url}')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
    }
    response = requests.get(url=url, headers=headers)
    logger.debug(f'Код ответа запроса на {url} : {response.status_code}')
    logger.info(f'Парсим полученную старничку')
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


def __parse_products(soup: BeautifulSoup, elem: str,
                     atr_name: str, atr_val: str) -> ResultSet:
    return soup.find_all(elem, attrs={atr_name: atr_val})


def __parse_next_page(soup: BeautifulSoup, elem: str,
                      atr_name: str, atr_val: str) -> Union[Tag, NavigableString]:
    return soup.find(elem, attrs={atr_name: atr_val})


def __parse_available(product: Tag, elem: str, atr_name: str, atr_val: str) -> bool:
    return False if product.parent.find(elem, attrs={atr_name: atr_val}) else True


def __parse_categories(soup: BeautifulSoup, elem: str,
                       atr_name: str, atr_val: str) -> Union[BeautifulSoup, NavigableString]:
    return soup.find(name=elem, attrs={atr_name: atr_val})


def __parse_weight(name: str) -> int:
    search_result = re.search(r'\d{1,4}', name[::-1])
    if search_result:
        return int(search_result.group()[::-1])
    else:
        return -1


def __clear_category_name(name: str) -> str:
    logger.info(f'Создаем список грязных частей названия')
    wrong_parts_name = (
        'Табак ', 'Безникотиновая Смесь ', 'Чайная смесь ',
        ', 100g/500g (тара)', ', 50g (пачка)', ', 200g (банка)', ' Medium 100g / 250g',
        ' Dark Line 100g', ', Special Edition 100g', ' 100g / CultT 500g', ', 30g', ', 50g', ', 100g', ', 1 kg',
        ' 40g', ' 50g', ' 100g', ' 250g',
    )
    logger.info(f'Проходимся по каждой грязной части')
    for wrong_part in wrong_parts_name:
        if wrong_part in name:
            logger.info(f'Удаляем грязь')
            name = name.replace(wrong_part, '')
    return name


def __fill_name_and_url(category: Tag, tabaks: list):
    logger.info(f'Очищаем "{category.text}"')
    logger.info(f'Создаем список игнорируемых категорий')
    ignore_categories = ('Безникотиновые заправки',)
    logger.info(f'Проходимся по каждой игнорируемой категории')
    for ignore_category in ignore_categories:
        logger.info(f'Проверяем категорию на игнор')
        if ignore_category in category.text:
            continue
        else:
            logger.info(f'Добавляем "{category.text}" в список')
            tabaks.append({
                'name': __clear_category_name(category.text),
                'url': category['href'],
            })


def __get_weight_kalyan_od_ua(url) -> set:
    weight = set()
    logger.info(f'Работаем с {url}')
    try:
        soup = __get_soup(url)
    except:
        return weight
    logger.info(f'Получаем ссылку на следующую страницу с табаками в категории')
    next_page = __parse_next_page(soup, 'ul', 'class', 'pagination')
    next_page = next_page.find('a', text='>') if next_page else next_page
    logger.info(f'Парсим все продукты на странице')
    products = __parse_products(soup, 'a', 'class', 'products__item-title')
    logger.info(f'Проходим по каждому продукту')
    for product in products:
        logger.info(f'Парсим есть ли он в наличии, если нет - переходим к следующему')
        if not __parse_available(product.parent.parent, 'mark', 'class', 'products__item-mark--nocatch'):
            continue
        logger.info(f'Парсим вес продукта из названия')
        weight.add(__parse_weight(product.text))
    if next_page:
        logger.info(f'Обнаружена следующая страница, рекурсионно повторяем процесс парсинга веса')
        weight.update(__get_weight_kalyan_od_ua(next_page['href']))
    return weight


def __parse_kalyan_od_ua(tabaks):
    url = 'https://kalyan.od.ua/'
    logger.info(f'Обрабатываем {url}')
    soup = __get_soup('https://kalyan.od.ua/tobacco')
    logger.info(f'Получаем список фирм табаков')
    categories = __parse_categories(soup, 'a', 'class', 'cat178').parent.ul.find_all('a')
    logger.info(f'Создаем пустой список для фирм табаков')
    logger.info(f'Проходим по каждой категории')
    for category in categories:
        logger.info(f'Заполняем имя фирмы табака "{category}" и ссылку на её страничку')
        __fill_name_and_url(category, tabaks)
    logger.info(f'Проходим по каждой фирме и парсим все веса, что есть')
    for tabak in tabaks:
        logger.info(f'Получаем список всех весов табака "{tabak["name"]}"')
        tabak['weight'] = __get_weight_kalyan_od_ua(tabak['url'])
    logger.info(f'Закончили с {url}')


def __get_weight_kalyan_in_ua(url) -> set:
    weight = set()
    logger.info(f'Работаем с {url}')
    try:
        soup = __get_soup(url)
    except:
        return weight
    logger.info(f'Получаем ссылку на следующую страницу с табаками в категории')
    next_page = __parse_next_page(soup, 'a', 'class', 'next i-next')
    logger.info(f'Парсим все продукты на странице')
    products = __parse_products(soup, 'p', 'class', 'product-name')
    logger.info(f'Проходим по каждому продукту')
    for product in products:
        if not __parse_available(product, 'p', 'class', 'availability'):
            continue
        logger.info(f'Парсим вес продукта из названия "{product.text}"')
        weight.add(__parse_weight(product.text))
    if next_page:
        logger.info(f'Обнаружена следующая страница, рекурсионно повторяем процесс парсинга веса')
        weight.update(__get_weight_kalyan_in_ua(next_page['href']))
    return weight


def __parse_kalyan_in_ua(tabaks):
    url = 'https://kalyan.in.ua/'
    logger.info(f'Обрабатываем {url}')
    soup = __get_soup('https://kalyan.in.ua/tabak-dlya-kalyana')
    logger.info(f'Получаем список фирм табаков')
    categories = __parse_categories(soup, 'div', 'class', 'amshopby-subcategories-wrapper').find_all('a')
    logger.info(f'Создаем пустой список для фирм табаков')
    logger.info(f'Проходим по каждой категории')
    for category in categories:
        logger.info(f'Заполняем имя фирмы табака "{category.text}" и ссылку на её страничку')
        __fill_name_and_url(category, tabaks)
    logger.info(f'Проходим по каждой фирме и парсим все веса, что есть')
    for tabak in tabaks:
        logger.info(f'Получаем список всех весов табака "{tabak["name"]}"')
        tabak['weight'] = __get_weight_kalyan_in_ua(tabak['url'])
    logger.info(f'Закончили с {url}')


def __remove_brace(n):
    return n[:n.find('(') - 1] if n.find('(') > 0 else n


def __remove_weight_dublicate(weights: str) -> str:
    weights = weights.split(',')
    weights = [int(w) for w in weights if w.isdigit()]
    weights = list(set(weights))
    weights.sort(key=lambda x: x)
    weights = map(lambda x: str(x), weights)
    weights = ','.join(weights)
    return weights


def start(req=None):
    logger.info('Инициализируем список словарей сайтов для БД')
    sites = [
        {
            'url': 'https://kalyan.in.ua/', 'title': 'kalyan.in.ua',
            'find_url': 'https://kalyan.in.ua/catalogsearch/result/?q={query}',
        },
        {
            'url': 'https://kalyan.od.ua/', 'title': 'kalyan.od.ua',
            'find_url': 'https://kalyan.od.ua/search?search={query}',
        },
    ]
    logger.info('Сохраняем список сайтов в БД')
    for site in sites:
        Site.objects.get_or_create(
            title=site['title'],
            url=site['url'],
            find_url=site['find_url'],
        )
    sites = Site.objects.all()
    tabaks = {}
    logger.info('Парсим сайты из списка')
    for site in sites:
        tabaks[site.url] = []
        globals()[f'__parse_{site.title.replace(".", "_")}'](tabaks[site.url])
    logger.info('Закончили парсить')
    logger.info('Проходимся по каждому спарсеному сайту')
    for site, tabaks_on_site in tabaks.items():
        logger.info(f'Сортируем список фирм табаков с сайта {site} по алфавиту')
        tabaks_on_site.sort(key=lambda x: x['name'])
        logger.info('Обрабатываем каждое наименование фирмы табака')
        for tabak in tabaks_on_site:
            tabak['name'] = __remove_brace(tabak['name'])
            logger.info(f'Добавляем "{tabak["name"].title()}" в общий список фирм табаков в БД')
            tabak_in_db, is_new = Tobacco.objects.get_or_create(
                title=tabak['name'].title(),
                defaults={
                    # сохраняем список весов в формате w0,w1,...,wn
                    'weight': ','.join([str(w) for w in tabak['weight']]),
                }
            )
            if not is_new:
                tabak_in_db.weight += f'{"," if tabak_in_db.weight else ""}' \
                                      f'{",".join([str(w) for w in tabak["weight"]])}' if tabak["weight"] else ''
                tabak_in_db.weight = __remove_weight_dublicate(tabak_in_db.weight)
                tabak_in_db.save()
            logger.info(f'Добавляем в список табаков для конкретного сайта "{site}" табак "{tabak_in_db}"')
            TobaccoOnSite.objects.get_or_create(
                title=tabak_in_db,
                site=sites.get(url=site),
                title_on_site=tabak['name'],
            )


class Command(BaseCommand):

    def handle(self, *args, **options):
        logger.info('Запуск процесса парсинга сайтов на табаки.')
        start()
        logger.info('Парсинг сайтов закончен.')
