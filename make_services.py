import json
import logging
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

class ServiceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.services = {}
        self.in_link = False
        self.current_href = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr_name, attr_value in attrs:
                if attr_name == 'href' and '/dienstleistung/' in attr_value:
                    self.current_href = attr_value.split('/')[-2]
                    self.in_link = True

    def handle_data(self, data):
        if self.in_link and self.current_href:
            self.services[self.current_href] = data.strip()

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_link = False


class LocationParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.in_label = False
        self.current_value = None
        self.locations = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            for attr_name, attr_value in attrs:
                if attr_name == 'value':
                    self.current_value = attr_value

        if tag == 'label':
            self.in_label = True

    def handle_data(self, data):
        if self.in_label and self.current_value:
            self.locations[self.current_value] = data.strip()
            self.current_value = None

    def handle_endtag(self, tag):
        if tag == 'label':
            self.in_label = False


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    with requests.Session() as session:
        session.headers = HEADERS

        response = session.get(f'https://service.berlin.de/dienstleistung/')

        parser = ServiceParser()
        parser.feed(response.text)
        services = parser.services

        locations = {}

        for pos, (service_idx, service_name) in enumerate(sorted(services.items(), key=lambda x: x[1])):
            logging.info('processing %s %s (%d out of %d)', service_idx, service_name, pos, len(services))
            response = session.get(f'https://service.berlin.de/dienstleistung/{service_idx}/')

            parser = LocationParser()
            parser.feed(response.text)

            locations[service_idx] = {
                'name': service_name,
                'locations': {
                    location_idx: location_name
                    for location_idx, location_name in sorted(parser.locations.items())
                    if location_idx != service_idx
                }
            }

    Path('services.json').write_text(json.dumps(locations, indent=4, sort_keys=True))
