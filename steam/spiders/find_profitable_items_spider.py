import json
import random
import time

import requests
import scrapy
from scrapy import Selector
from scrapy.crawler import CrawlerProcess
from selenium import webdriver

import sys

from selenium.webdriver.common.proxy import ProxyType, Proxy
from selenium.webdriver.firefox.options import Options

sys.path.insert(0, "/home/botadd/PycharmProjects/SS/steam/")


class ProxyMixin:
    def get_proxy_generator(self):
        with open('proxies.txt', 'r') as f:
            self.proxy_list = [p.strip() for p in f.readlines()]
        self.proxy_generator = (proxy for proxy in self.proxy_list)

    def restore_generator(self):
        random.shuffle(self.proxy_list)
        self.proxy_generator = (proxy for proxy in self.proxy_list)

    def get_proxy(self):
        try:
            proxy = self.proxy_generator.__next__()
        except StopIteration:
            self.restore_generator()
            proxy = self.proxy_generator.__next__()
        return proxy


class ExtractItemsLinksSpider(ProxyMixin, scrapy.Spider):
    name = 'price_search'
    market_items_list_url = 'https://steamcommunity.com/market/search/render/?query=&start={start}&count={count}&search_descriptions=0&sort_column=popular&sort_dir=desc&appid=730&category_730_ItemSet%5B%5D=any&category_730_ProPlayer%5B%5D=any&category_730_StickerCapsule%5B%5D=any&category_730_TournamentTeam%5B%5D=any&category_730_Weapon%5B%5D=any&category_730_Exterior%5B%5D=tag_WearCategory2&category_730_Exterior%5B%5D=tag_WearCategory1&category_730_Exterior%5B%5D=tag_WearCategory4&category_730_Exterior%5B%5D=tag_WearCategory3&category_730_Exterior%5B%5D=tag_WearCategory0&category_730_Exterior%5B%5D=tag_WearCategoryNA'
    max_query_size = 100
    obtained = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_proxy_generator()
        self.rotate_proxy = False

    def get_page_numbers(self, total_count):
        if total_count % self.max_query_size == 0:
            return total_count // self.max_query_size
        return (total_count // self.max_query_size) + 1

    def get_page_size_parameters(self, page_counter):
        params = (page_counter * self.max_query_size, self.max_query_size)
        return params

    def start_requests(self):
        first_response = requests.get(self.market_items_list_url.format(start=10, count=10))
        total_count = 9200 #int(first_response.json().get('total_count'))
        requests_list = []
        for page_counter in range(self.get_page_numbers(total_count)):
            start, count = self.get_page_size_parameters(page_counter)
            next_page = self.market_items_list_url.format(start=start, count=count)
            pr = self.get_proxy()
            requests_list.append(scrapy.Request(url=next_page, dont_filter=True, meta={'proxy': None}, callback=self.parse))
        return requests_list

    def parse(self, response, *args, **kwargs):
        try:
            json_response = json.loads(response.body_as_unicode())
            if json_response:
                html = json_response.get('results_html')
                if html:
                    item_div_elements = Selector(text=html).xpath('//a[@class="market_listing_row_link"]').getall()

                    if item_div_elements:
                        type(self).obtained += len(item_div_elements)
                        print('LEN', type(self).obtained)
                        with open('all_item_links.txt', 'a') as f:
                            for item in item_div_elements:
                                item_quantity = Selector(text=item).xpath(
                                    '//span[@class="market_listing_num_listings_qty"]/@data-qty').get()
                                if int(item_quantity) > 200:
                                    href = Selector(text=item).xpath('//@href').get()
                                    f.write(href + '\n')
                yield {}
        except Exception as e:
            print(e)

        print('FAIL')
        yield scrapy.Request(url=response.url, dont_filter=True, callback=self.parse, meta={'proxy': self.get_proxy()})


class GetProfitableItemsSpider(ProxyMixin, scrapy.Spider):
    name = 'get_profitable_items'
    items_query_url_part = '/render/?query=&start={start}&count={count}&country=US&language=english&currency=1'

    def __init__(self, start_requests_count=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No GUI for selenium
        self.firefox_options = Options()
        self.firefox_options.headless = True

        self.get_proxy_generator()
        with open('all_item_links.txt', 'r') as f:
            self.link_generator = (link for link in f.readlines())
        self.start_requests_count = start_requests_count

    def start_requests(self):
        r_list = []
        for _ in range(self.start_requests_count):
            url = self.link_generator.__next__() + self.items_query_url_part.format(start=0, count=20)
            r = scrapy.Request(
                url,
                dont_filter=True,
                meta={'proxy': self.get_proxy()},
                callback=self.parse,
                errback=self.error_handler
            )
            r_list.append(r)

        return r_list

    def error_handler(self, failure):
        print('ERRR')
        yield scrapy.Request(
            url=failure.request.url,
            meta={'proxy': self.get_proxy()},
            dont_filter=True,
            callback=self.parse,
            errback=self.error_handler
        )

    def get_proxy_for_driver(self, proxy):
        print('PROX', proxy)
        proxy = proxy.split('https://')[1]
        proxy = Proxy({
            'proxyType': ProxyType.MANUAL,
            'httpProxy': proxy,
            'ftpProxy': proxy,
            'sslProxy': proxy,
            'noProxy': ''
        })
        return proxy

    def get_minimum_price(self, driver):
        min_buy_orders = driver.find_element_by_xpath('//div[@id="market_commodity_buyrequests"]')
        print('asas', min_buy_orders)
        # Need to sleep
        time.sleep(1.5)
        if min_buy_orders.text:
            print(min_buy_orders)
            # Beautiful
            min_buy_price = float([e for e in min_buy_orders.text.split() if e.startswith('$')][0].split('$')[1])
            return min_buy_price
        else:
            raise Exception('LOL1')

    def close_driver(self, driver):
        try:
            driver.close()
        except:
            pass

    def parse(self, response):
        # At first we get medium prices
        driver = None
        try:
            json_response = json.loads(response.body_as_unicode())
            items = list(json_response['listinginfo'].values())
            prices_sum = sum([item['converted_price_per_unit'] + item['converted_fee_per_unit'] for item in items])
            medium_price = round(prices_sum / (len(items) * 100), 2)
        except Exception as e:
            print('EXC::', e)
            yield scrapy.Request(
                response.request.url,
                meta={'proxy': self.get_proxy()},
                dont_filter=True,
                callback=self.parse,
                errback=self.error_handler,
            )
        else:
            for i in range(3):
                try:
                    proxy_obj = self.get_proxy_for_driver(response.request.meta['proxy'])
                    driver = webdriver.Firefox(options=self.firefox_options, proxy=proxy_obj)
                    driver.get(response.url.split('/render')[0])
                    minimum_price = self.get_minimum_price(driver)
                    print('MIN:', minimum_price, 'MED:', medium_price, response.url)
                except Exception as e:
                    self.close_driver(driver)
                    print('SELEN EXC::', e)
                    time.sleep(10)
                    continue
                else:
                    self.close_driver(driver)
                    if minimum_price > 0.1:
                        if (minimum_price * 1.15) + 0.01 < medium_price:
                            with open('res.txt', 'a') as f:
                                additional_data = f'MIN: {minimum_price} MED: {medium_price}'
                                f.write(response.url + additional_data + '\n')
                    break
            else:
                with open('res.txt', 'a') as f:
                    f.write('FAIL TO GET MIN PRICE: ' + response.url + '\n')
        # For safety
        self.close_driver(driver)
        try:
            next_url = self.link_generator.__next__() + self.items_query_url_part.format(start=0, count=20)
            yield scrapy.Request(
                next_url,
                meta={'proxy': self.get_proxy()},
                dont_filter=True,
                callback=self.parse,
                errback=self.error_handler,
            )
        except StopIteration:
            yield {}




process = CrawlerProcess({
        'DOWNLOAD_TIMEOUT': 10,
        'ITEM_PIPELINES': {'steam.pipelines.SteamPipeline': 300},
        'USER_AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
        'DOWNLOADER_MIDDLEWARES': {
            'steam.middlewares.PriceMonitorRetryMiddleware': 550,
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
        },
        'DOWNLOAD_DELAY': 3,
        # 'SPIDER_MIDDLEWARES': {
        #     'steam.middlewares.PricingSearchSpiderMiddleware': 1000
        # },
        # 'LOG_LEVEL': 'INFO',
        'RETRY_TIMES': 1,
        # 'LOG_ENABLED': False
    })

# process.crawl(ExtractItemsLinksSpider)
process.crawl(GetProfitableItemsSpider)
process.start()
