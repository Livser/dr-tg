from grab.error import GrabTimeoutError
from telepot import Bot
import settings
import re
import time
from raven import Client

from parser import Parser, HELP_TEXT
from views import sector_text, KoImg

CORD_RE = '([35]\d[\.,]\d+)'
STANDARD_CODE_PATTERN = '\d*[dдrрDДRР]\d*[dдrрDДRР]\d*'


# STANDARD_CODE_PATTERN = '(?:([1-9]+))?(?:([dд])|[rр])(?:([1-9]+))?(?(2)[rр]|[dд])(?(1)[1-9]*|(?(3)[1-9]*|[1-9]+))'
# STANDARD_CODE_PATTERN = '\b\d*[dд]\d*[rр]\d*(?<=\w\w\w)\b|\b\d*[rр]\d*[dд]\d*(?<=\w\w\w)\b'


class DzrBot(Bot):
    parse = False  # Режим парсинга движка
    type = False  # Режим ввода кодов
    sentry = None
    convert_dr = True

    routes = (
        (CORD_RE, 'on_cord'),
        (r'^/ko', 'on_ko'),
        (r'^/auth', 'on_auth'),
        (r'^/link', 'on_link'),
        (r'^/test_ko_img', 'on_test_ko_img'),
        (r'^/test_error', 'on_test_error'),
        (r'^/help', 'on_help'),
        (r'^/type', 'on_type'),
        (r'^/parse', 'on_parse'),
        (r'^/convert_dr', 'on_convert_dr'),
        (r'^/cookie', 'on_cookie'),
        (r'^/pin', 'on_pin'),
        (r'^/pattern', 'on_pattern'),
        (r'^/status', 'on_status'),
    )

    def set_data(self, key, value):
        setattr(self, key, value)
        self.parser.table_bot.upsert({
            'token': settings.TOKEN,
            key: value
        }, ['token'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = Parser()
        if hasattr(settings, 'SENTRY_DSN') and settings.SENTRY_DSN:
            self.sentry = Client(settings.SENTRY_DSN)

        self.parser.table_bot.upsert({'token': settings.TOKEN}, ['token'])
        data = self.parser.table_bot.find_one(**{'token': settings.TOKEN})
        for key in [
            'type',
            'parse',
        ]:
            value = data.get(key)
            if value is not None:
                setattr(self, key, value)

        cookie = data.get('cookie')
        if cookie:
            self.parser.set_cookie(cookie)

        pin = data.get('pin')
        if pin:
            self.parser.set_pin(pin)

        code_pattern = data.get('code_pattern')
        if code_pattern:
            self.code_pattern = code_pattern
        else:
            self.code_pattern = STANDARD_CODE_PATTERN

    def on_help(self, chat_id, text, **kwargs):
        self.sendMessage(chat_id, HELP_TEXT)

    def on_type(self, chat_id, text, **kwargs):
        if 'on' in text:
            self.set_data('type', True)
        elif 'off' in text:
            self.set_data('type', False)
        self.sendMessage(chat_id, "Режим ввода кодов: {}".format("Включен" if self.type else "Выключен"))

    def on_parse(self, chat_id, text, **kwargs):
        if 'on' in text:
            self.set_data('parse', True)
        elif 'off' in text:
            self.set_data('parse', False)
        self.sendMessage(chat_id, "Режим парсинга движка: {}".format("Включен" if self.parse else "Выключен"))

    def on_convert_dr(self, chat_id, text, **kwargs):
        if 'on' in text:
            self.set_data('convert_dr', True)
        elif 'off' in text:
            self.set_data('convert_dr', False)
        self.sendMessage(chat_id, "Режим изменения д->d, р->r: {}".format("Включен" if self.convert_dr else "Выключен"))

    def on_cookie(self, chat_id, text, **kwargs):
        for cookie in re.findall('(\w{24})', text):
            self.parser.set_cookie(cookie)
            self.set_data('cookie', cookie)
            self.sendMessage(chat_id, "Кука установлена")

    def on_test_ko_img(self, chat_id, text, **kwargs):
        self.send_ko_img(chat_id)

    def on_test_error(self, chat_id, text, **kwargs):
        raise Exception

    def on_auth(self, chat_id, text, **kwargs):
        try:
            login, password = map(
                lambda x: x.strip(),
                filter(
                    bool,
                    text.replace('/auth', '').split(' ')
                )
            )
        except ValueError:
            return
        self.parser.auth(login, password)
        self.sendMessage(chat_id, 'Авторизация установлена. Логин = {}'.format(login))

    def on_ko(self, chat_id, text, **kwargs):
        self.send_ko(chat_id)

    def on_pin(self, chat_id, text, **kwargs):
        text = text.replace('/pin', '').strip()
        if text:
            self.parser.set_pin(text)
            self.set_data('pin', text)
            self.sendMessage(chat_id, "Пин установлен")
        else:
            data = self.parser.table_bot.find_one(**{'token': settings.TOKEN})
            pin = data.get('pin')
            if pin:
                self.sendMessage(chat_id, "Пин есть: {}")
            else:
                self.sendMessage(chat_id, "Пин отсутствует")

    def on_pattern(self, chat_id, text, **kwargs):
        text = text.replace('/pattern', '').strip()
        if 'standar' in text:
            text = STANDARD_CODE_PATTERN

        if text:
            try:
                re.compile(text)
            except re.error:
                self.sendMessage(chat_id, "Шаблон кода не установлен")

            self.set_data('code_pattern', text)
            self.sendMessage(chat_id, "Шаблон кода установлен: {}".format(text))
        else:
            self.sendMessage(chat_id, "Шаблон кода: {}".format(self.code_pattern))

    def on_link(self, chat_id, text, **kwargs):
        data = self.parser.table_bot.find_one(**{'token': settings.TOKEN})
        text = text.replace('/link', '').strip()
        if text:
            self.set_data('link', text)
            self.sendMessage(chat_id, "Установлена ссылка {}".format(text))
        else:
            link = data.get('link')
            if link:
                self.sendMessage(chat_id, "Ссылка: {}".format(link))
            else:
                self.sendMessage(chat_id, "Настройки ссылки не найдено")

    def on_cord(self, chat_id, text, **kwargs):
        cord_list = re.findall(CORD_RE, text)
        if len(cord_list) == 2:
            self.sendLocation(chat_id, *cord_list)

    def process_one_code(self, chat_id, code, message_id):
        try:
            self.parser.fetch(code, convert_dr=self.convert_dr)
        except GrabTimeoutError:
            self.sendMessage(chat_id, "Проблема подключения к движку")
            return
        parse_result = self.parser.parse()

        server_message = parse_result.get('message', '').lower()
        if server_message:
            self.sendMessage(chat_id, "{} : {}".format(code, server_message), reply_to_message_id=message_id)

        self.parse_and_send(parse_result)

    def on_code(self, chat_id, text, message_id):
        code_list = re.findall(self.code_pattern, text, flags=re.I)

        for code in code_list:
            if len(code) < 3:
                continue
            self.process_one_code(chat_id, code, message_id)

    def on_status(self, chat_id, text, **kwargs):
        message = ''

        try:
            self.parser.fetch()
        except GrabTimeoutError:
            self.sendMessage(chat_id, "Проблема подключения к движку")
            return

        body = self.parser.g.doc.body.decode('cp1251')
        message += 'Движок {}\n'.format("включен" if 'лог игры' in body.lower() else 'выключен')
        message += 'Режим парсинга движка {}\n'.format("включен" if self.parse else "выключен")
        message += 'Режим ввода кодов {}\n'.format("включен" if self.type else "выключен")
        message += 'Режим замены д->d р->r {}'.format("включен" if self.convert_dr else "выключен")

        self.sendMessage(chat_id, message, reply_to_message_id=kwargs.get('message_id'))

    def _on_chat_message(self, msg):
        text = msg.get('text')
        message_id = msg.get('message_id')
        if text is None:
            return
        chat_id = msg['chat'].get('id')

        # Отвечает не собеседнику, а в определенный чат, если в settings этот чат задан явно.
        if hasattr(settings, 'CHAT_ID'):
            if chat_id and chat_id != settings.CHAT_ID:
                return
            else:
                chat_id = settings.CHAT_ID

        for pattern, method_str in self.routes:
            method = getattr(self, method_str, None)
            if method is not None and re.search(pattern, text):
                method(chat_id, text, message_id=message_id)

        if self.type and 2 < len(text) < 100 and re.search(self.code_pattern, text, flags=re.I):
            self.on_code(chat_id, text.strip().lower(), message_id=message_id)

        if self.type and text[:2] == '/ ':
            self.process_one_code(
                chat_id,
                text.replace('/ ', '').strip().replace(' ', '').lower(),
                message_id=message_id,
            )

    def on_chat_message(self, msg):
        if self.sentry:
            try:
                self._on_chat_message(msg)
            except Exception as exc:
                self.sentry.captureException(exc_info=True)
        else:
            self._on_chat_message(msg)

    def send_ko(self, channel_id):
        for sector in self.parser.table_sector.all():
            sector['code_list'] = list(self.parser.table_code.find(sector_id=sector['id']))
            self.sendMessage(channel_id, sector_text(sector), parse_mode='Markdown')

    def send_ko_img(self, channel_id):
        for sector in self.parser.table_sector.all():
            ko_list = list(self.parser.table_code.find(sector_id=sector['id']))
            ko_img = KoImg(ko_list=ko_list)
            self.sendPhoto(channel_id, ('ko.png', ko_img.content))

    def handle_loop(self):
        if not self.parse:
            return
        try:
            self.parser.fetch()
        except GrabTimeoutError:
            return
        parse_result = self.parser.parse()
        self.parse_and_send(parse_result)

    def parse_and_send(self, parse_result):
        channel_id = getattr(settings, 'CHANNEL_ID', None)
        if channel_id is None:
            return

        if parse_result['new_level']:
            self.sendMessage(channel_id, 'Новый уровень')
            self.send_ko(channel_id)

            # Сбрасываем паттерн
            self.code_pattern = STANDARD_CODE_PATTERN
            self.set_data('code_pattern', STANDARD_CODE_PATTERN)

        for tip in parse_result['tip_list']:
            self.sendMessage(channel_id, "Подсказка: {}".format(tip['text']))

        if parse_result['new_code']:
            self.send_ko(channel_id)

        if parse_result['new_spoiler']:
            self.sendMessage(channel_id, 'Открыт спойлер')


if __name__ == '__main__':
    bot = DzrBot(settings.TOKEN)
    bot.message_loop()
    while 1:
        bot.handle_loop()
        time.sleep(getattr(settings, 'SLEEP_SECONDS', 30))
