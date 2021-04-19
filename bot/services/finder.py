import requests
from loguru import logger
# noinspection PyProtectedMember
from bs4 import BeautifulSoup, NavigableString
from bot.models import Site
import urllib.parse


def __get_soup(url: str, q: str, uid: int) -> BeautifulSoup:
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
    full_url = url.format(query=urllib.parse.quote_plus(q))
    logger.info(f'[{uid}]|Переходим по ссылке {full_url}.')
    response = requests.get(url=full_url, headers=headers)
    logger.debug(f'Код ответа запроса на {response.url} : {response.status_code}')
    logger.info(f'[{uid}]|Парсим полученную старничку.')
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


def __parse_kalyan_in_ua(soup, uid: int):
    logger.info(f'[{uid}]|Парсим все табаки.')
    products = soup.find('ul', attrs={'class': 'products-grid'}).find_all('li', attrs={'class': 'item'})
    result = []
    if soup.find('p', attrs={'class': 'misspell'}):
        logger.info(f'[{uid}]|Табаки отсутствуют.')
        return result
    logger.info(f'[{uid}]|Парсим наличие табаков. Если табак в наличии - сохраняем.')
    for product in products:
        if not product.find('p', attrs={'class': 'availability'}):
            result.append({
                'name': product.p.a.text,
                'link': product.p.a['href'],
                'price': product.find('span', attrs={'class': 'price'}).text,
            })
    logger.info(f'[{uid}]|Закончили парсить список табаков.')
    return result


def __parse_kalyan_od_ua(soup, uid: int):
    logger.info(f'[{uid}]|Парсим все табаки.')
    products = soup.find('div', attrs={'class': 'products__grid'})
    result = []
    if not products:
        logger.info(f'[{uid}]|Табаки отсутствуют.')
        return result
    else:
        products = products.find_all('div', attrs={'class': 'products__item'})
    logger.info(f'[{uid}]|Парсим наличие табаков. Если табак в наличии - сохраняем.')
    for product in products:
        sold = product.find('div', attrs={'class': 'products__item-stickers'})
        sold = sold.find('mark', attrs={'class': 'products__item-mark--catch'})
        sold = sold.text if sold else sold
        if sold != 'ПРОДАНО!':
            result.append({
                'name': product.find('div', attrs={'class': 'products__item-desc'}).a.text,
                'link': product.find('div', attrs={'class': 'products__item-desc'}).a['href'],
                'price': ''.join([
                    p.strip() for p in product.find('div', attrs={'class': 'products__item-desc'}).span.contents
                    if type(p) == NavigableString
                ]),
            })
    logger.info(f'[{uid}]|Закончили парсить список табаков.')
    return result


def start(company: str, flavor: str, extra: str, uid: int) -> str:
    logger.info(f'[{uid}]|Процесс парсинга сайтов по запросу.')
    q = f'{company} {"" if flavor.lower() == "все" else flavor} {extra}'
    sites = Site.objects.all()
    text = ''
    template = '[{name}]({link}) — {price}\n'
    products = []
    for site in sites:
        soup = __get_soup(site.find_url, q=q, uid=uid)
        products += globals()[f'__parse_{site.title.replace(".", "_")}'](soup, uid=uid)
    logger.info(f'[{uid}]|Формируем ответ со списком найденных табаков.')
    for site in sites:
        tabaks_list = ''
        for product in products:
            if site.title not in product['link'] or extra not in product['name']:
                continue
            tabaks_list += template.format(
                name=product['name'],
                link=product['link'],
                price=product['price'],
            )
        if tabaks_list != '':
            tabaks_list = f'\N{fire}`{site.title.capitalize()}`\n' + tabaks_list + '\n'
        text += tabaks_list
    logger.info(f'[{uid}]|Формируем ответ со списком найденных табаков — готово.')
    return text
