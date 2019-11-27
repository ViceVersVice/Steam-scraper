import json
import random
import time
from json import JSONDecodeError
from queue import Queue

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


import sys
sys.path.insert(0, "/home/botadd/PycharmProjects/SS/steam/")

from steam.spiders.callbacks import CallBacks


class PriceMonitor(scrapy.Spider):
    name = 'price_monitor'

    def get_item_name(self, loaded_json):
        items_name_list = loaded_json.get('assets').get('730').get('2')
        try:
            item_name = next(iter(items_name_list.values()))['name']
        except (TypeError, KeyError):
            print('FAILED TO GET ITEM NAME')
            return
        self.scrape_runner.item_name = item_name

    def parse(self, response):
        print('REQ STAT', response.status, type(response.status), 'META:', response.request._meta)
        ret = {'item_id': None, 'found': False}
        try:
            loaded_json = json.loads(response.body_as_unicode())
        except JSONDecodeError:
            print('FAIL TO LOAD JSON!')
            self.scrape_runner.rotate_proxy = True
            return ret

        if not self.scrape_runner.item_name:
            self.get_item_name(loaded_json)
            print('ITEM NAEM:', self.scrape_runner.item_name)

        items = list(loaded_json['listinginfo'].values())
        medium_price_without_first_item = sum([item['converted_price_per_unit'] + item['converted_fee_per_unit'] for item in items[1:]]) / (len(items) - 1)
        # The first one has minimum price
        minimum_price = items[0]['converted_price_per_unit'] + items[0]['converted_fee_per_unit']

        print("MIN PRICE", minimum_price, '\n', "MEdium PRICE", medium_price_without_first_item, self.scrape_runner.minimum_coefficient)
        item_id = items[0]['listingid']
        if minimum_price/medium_price_without_first_item < self.scrape_runner.minimum_coefficient:
            print('NO WAY!!!!', item_id)
            params = {
                'item_id': item_id,
                'min_price': minimum_price,
                'med_price': medium_price_without_first_item,
                'item_name': self.scrape_runner.item_name,
                'inventory_url': self.scrape_runner.inventory_url,
                'items_listing_url': self.scrape_runner.items_listing_url,
            }
            self.scrape_runner.buy_and_sell_queue.put(params)
        yield ret


class AllPricesSpider(scrapy.Spider):
    name = 'all_prices'
    max_query_size = 100
    url_template = 'https://steamcommunity.com/market/listings/730/AWP%20%7C%20Wildfire%20%28Field-Tested%29/render/?query=&start={start}&count={count}&country=PL&language=english&currency=6'
    start_urls = [
        url_template.format(start=0, count=10),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_count = None
        self.page_counter = 0
        self.responses = []
        self.yielded = False

    def get_total_count(self, response):
        loaded_json = json.loads(response.body_as_unicode())
        count = loaded_json.get('total_count')
        self.total_count = count if count <= 1000 else 1000

    def get_page_size_parameters(self):
        params = (self.page_counter * self.max_query_size, self.max_query_size)
        return params

    def get_page_numbers(self):
        if self.total_count % self.max_query_size == 0:
            return self.total_count // self.max_query_size
        return (self.total_count // self.max_query_size) + 1

    def parse(self, response):
        # if not self.total_count:
        self.get_total_count(response)
        print('TC', self.total_count)
        print('--------------------------START--------------------------------')
        # self.yielded = False
        self.page_counter = 0
        for i in range(self.get_page_numbers()):
            start, count = self.get_page_size_parameters()
            print(f'--------------------------START_{self.page_counter}--------------------------------')
            time.sleep(3)
            self.page_counter += 1
            print('STRT:', start, 'CNT:', count)
            next_page = self.url_template.format(start=start, count=count)
            yield scrapy.Request(url=next_page, callback=self.get_all_prices,
                                 meta={'ident': self.page_counter}, dont_filter=True)

    def get_all_prices(self, response):
        ident = response.meta["ident"]
        loaded_json = json.loads(response.body_as_unicode())

        try:
            prices = [item['converted_price_per_unit'] + item['converted_fee_per_unit'] for item in loaded_json['listinginfo'].values()]
        except KeyError as e:
            # TODO
            pass
        time.sleep(2)
        print(f'--------------------------YIELD_{ident}--------------------------------')
        self.responses.append(ident)
        yield {'prices': prices}


class ScrapingRunner:
    buy_and_sell_queue = Queue()
    settings = get_project_settings()
    process = CrawlerProcess({
        'DOWNLOAD_TIMEOUT': 15,
        'ITEM_PIPELINES': {'steam.pipelines.SteamPipeline': 300},
        'USER_AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
        'DOWNLOADER_MIDDLEWARES': {
            'steam.middlewares.SteamDownloaderMiddleware': 90,
            'steam.middlewares.PriceMonitorRetryMiddleware': 550,
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
        },
        'SPIDER_MIDDLEWARES': {
            'steam.middlewares.SteamSpiderMiddleware': 1000
        },
        # 'LOG_LEVEL': 'INFO',
        'RETRY_TIMES': 1,
        'LOG_ENABLED': False
    })

    def __init__(self, spider_cls, items_listing_url, minimum_coefficient):
        self.spider_cls = spider_cls
        self.item_name = ''
        self.minimum_coefficient = minimum_coefficient

        self.items_listing_url = items_listing_url
        self.items_query_url_part = 'render/?query=&start={start}&count={count}&country=PL&language=english&currency=6'
        self.inventory_url = 'https://steamcommunity.com/profiles/76561198081196956/inventory#730'
        self.start_urls = [
            self.items_listing_url + self.items_query_url_part.format(start=0, count=20)
        ]

        self.rotate_proxy = False
        with open('proxies.txt', 'r') as f:
            self.proxy_list = [p.strip() for p in f.readlines()]

        self.proxy_list.append(None)
        # Perform shuffle to not owerload one proxy with many requests --> prevents timeout
        random.shuffle(self.proxy_list)
        self.active_proxy = self.proxy_list[0]
        self.proxy_generator = (proxy for proxy in self.proxy_list)

    def restore_generator(self):
        random.shuffle(self.proxy_list)
        self.proxy_generator = (proxy for proxy in self.proxy_list)

    def crawl_loop(self, result):
        # Adding self as kwarg --> inside spider instance we will have access to runner data
        deferred = self.process.crawl(self.spider_cls, start_urls=self.start_urls,
                                      scrape_runner=self)
        deferred.addCallback(CallBacks.buy_and_sell, self.buy_and_sell_queue)
        deferred.addCallback(CallBacks._sleep, seconds=3)
        deferred.addCallback(self.crawl_loop)
        return deferred

    def run(self):
        self.crawl_loop(None)


with open('/home/botadd/PycharmProjects/SS/steam/steam/spiders/item_urls.json', 'r') as f:
    for item in json.loads(f.read()):
        url = item['url']
        minimum_coefficient = item['minimum_coefficient'] if item['minimum_coefficient'] else 0.82
        ScrapingRunner(PriceMonitor, url, minimum_coefficient).run()

ScrapingRunner.process.start()
