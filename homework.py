import logging
import os
import time
from logging.handlers import RotatingFileHandler
from http import HTTPStatus
import requests
from requests.exceptions import RequestException

import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(name)s, %(message)s',
)
logger = logging.getLogger('__name__')
handler = RotatingFileHandler('homework.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRAKTIKUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 300
RETRY_ERROR_TIME = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message: str) -> None:
    logging.info(f'Отправка сообщения: {message} на CHAT_ID: {CHAT_ID}')
    try:
        return bot.send_message(chat_id=CHAT_ID, text=message)
    except telegram.error.TelegramError as sending_error:
        logging.error(f'Ошибка отправки Telegram: {sending_error}')


def get_api_answer(url, current_timestamp):
    current_timestamp = current_timestamp
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    params = {
        'from_date': current_timestamp,
    }
    try:
        homework_statuses = requests.get(
            url, params=params, headers=headers
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise HTTPStatus.Internal_server_error(
                f'Ошибка {homework_statuses}')
        return homework_statuses.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        logging.error(f'Ошибка {error}')
    return {}


def check_response(response):
    try:
        homeworks = response.get('homeworks')
        if len(homeworks) == 0:
            raise KeyError('Ошибка, нет домашек')
        return homeworks
    except RequestException:
        raise RequestException('Ошибка запроса')


def parse_status(homework):
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_STATUSES:
        return f'Изменился статус проверки работы "{homework_name}".' \
               f' {HOMEWORK_STATUSES[homework_status]}'
    else:
        raise ValueError('Ошибка неверное значение статуса при парсинге')


def check_tokens():
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, CHAT_ID]
    for token in tokens:
        if token is None:
            return False
    return True


def main():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    logging.info('Бот начинает работу')
    while True:
        try:
            new_homework = get_api_answer(ENDPOINT, current_timestamp)
            logging.info('checking response')
            if check_response(new_homework):
                logging.info('Отправка сообщения')
                send_message(
                    bot, parse_status(new_homework.get('homeworks')[0])
                )
            current_timestamp = new_homework.get(
                'current_date', current_timestamp
            )
            logging.info('Запрос создан')
            time.sleep(RETRY_TIME)
        except Exception as error:
            logger.error(error, exc_info=True)
            logging.error('Ошибка пустой список, либо ошибка сервера')
            time.sleep(RETRY_TIME)
            continue


if __name__ == '__main__':
    if check_tokens():
        main()
