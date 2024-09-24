import json
import logging
import time
import webbrowser
from html.parser import HTMLParser
from pathlib import Path

import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8',
    'Accept-Language': 'en,ru;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'DNT': '1',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i'
}


class TitleParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title = data


class CalendarLinkParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.in_td = False
        self.links = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
        if tag == 'a' and self.in_td:
            href = None
            title = None
            for attr_name, attr_value in attrs:
                if attr_name == 'href' and '/terminvereinbarung/termin/time/' in attr_value:
                    href = attr_value
                if attr_name == 'title':
                    title = attr_value
            if href and title:
                self.links[title] = href

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td = False


class TimeLinkParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.current_time = None
        self.current_title = None
        self.current_href = None
        self.in_buchbar = False
        self.in_frei = False
        self.data = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'th':
            for attr_name, attr_value in attrs:
                if attr_name == 'class' and attr_value == 'buchbar':
                    self.in_buchbar = True

        if tag == 'td':
            for attr_name, attr_value in attrs:
                if attr_name == 'class' and attr_value == 'frei':
                    self.in_frei = True

        if tag == 'a' and self.in_frei:
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    self.current_href = attr_value

    def handle_data(self, data):
        if self.in_buchbar:
            self.current_time = data.strip()
        if self.in_frei:
            self.current_title = data.strip()

    def handle_endtag(self, tag):
        if tag == 'th':
            self.in_buchbar = False
        if tag == 'a':
            self.in_frei = False
            if self.current_time and self.current_title and self.current_href:
                self.data[f'{self.current_time} - {self.current_title}'] = self.current_href
            self.current_time = None
            self.current_title = None
            self.current_href = None


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    services = json.loads(Path('services.json').read_text())

    with requests.Session() as session:
        session.headers = HEADERS

        # Anmeldung einer Wohnung
        my_service = '120686'

        url = 'https://service.berlin.de/terminvereinbarung/termin/restart/'
        params = {
            'providerList': ','.join(services[my_service]['locations']),
            'requestList': my_service
        }

        response = None


        def wait_for_termin():
            global response
            response = session.get(url, params=params)

            return response.url == 'https://service.berlin.de/terminvereinbarung/termin/taken/'


        while wait_for_termin():
            time.sleep(30)

        time.sleep(1)

        parser = CalendarLinkParser()
        parser.feed(response.text)

        for title, link in parser.links.items():
            logging.info('%s - https://service.berlin.de/%s', title, link)

        earliest = next(iter(parser.links.values()))
        url = f'https://service.berlin.de/{earliest}'

        response = session.get(url)

        parser = TimeLinkParser()
        parser.feed(response.text)

        for title, link in parser.data.items():
            logging.info('%s - https://service.berlin.de%s', title, link)

        earliest = next(iter(parser.data.values()))
        url = f'https://service.berlin.de/{earliest}'

        time.sleep(1)

        response = session.get(url)

        logging.info('1. Open %s', response.url)
        logging.info('2. Set cookie in the browser:')

        for cookie in session.cookies:
            logging.info('%s: %s', cookie.name, cookie.value)

        webbrowser.open(response.url)
