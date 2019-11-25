import json
import time

import scrapy
from scrapy import signals
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


class SteamSpider(scrapy.Spider):
    name = 'steam'
    max_query_size = 100
    url_template = 'https://steamcommunity.com/market/listings/730/Glock-18%20%7C%20Water%20Elemental%20%28Minimal%20Wear%29/render/?query=&start={start}&count={count}&country=PL&language=english&currency=1'
    start_urls = [
        url_template.format(start=0, count=10),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_count = None
        self.page_counter = 0

    # @classmethod
    # def from_crawler(cls, crawler, *args, **kwargs):
    #     spider = super().from_crawler(crawler, *args, **kwargs)
    #     crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
    #     return spider
    # #
    # def spider_closed(self, spider):
    #     spider.logger.info('Spider closed: %s', spider.name)

    def get_total_count(self, response):
        loaded_json = json.loads(response.body_as_unicode())
        self.total_count = loaded_json.get('total_count')

    def get_page_size_parameters(self):
        params = (self.page_counter * self.max_query_size, self.max_query_size)
        return params

    def get_page_numbers(self):
        if self.total_count % self.max_query_size == 0:
            return self.total_count // self.max_query_size
        return (self.total_count // self.max_query_size) + 1

    def parse(self, response):
        self.get_total_count(response)
        print('TC', self.total_count)

        for i in range(self.get_page_numbers()):
            start, count = self.get_page_size_parameters()
            self.page_counter += 1
            print('STRT:', start, 'CNT:', count)
            next_page = self.url_template.format(start=start, count=count)
            print('URL', start, count)

            yield scrapy.Request(url=next_page, callback=self.get_price_mediana, meta={'ident': self.page_counter})

    def get_price_mediana(self, response):
        ident = response.meta["ident"]
        loaded_json = json.loads(response.body_as_unicode())
        prices = [item['converted_price_per_unit'] + item['converted_fee_per_unit'] for item in loaded_json['listinginfo'].values()]
        time.sleep(2)
        yield {'prices': prices}
        # yield scrapy.Request(url=response.url, callback=self.get_price_mediana, meta={'ident': ident})

result = []
def collect(item, response, spider):
    result.extend(item['prices'])
    # print('IN COLLECT:', item)

settings = get_project_settings()
process = CrawlerProcess({
    'ITEM_PIPELINES': {'steam.pipelines.SteamPipeline': 300},
})
process.crawl(SteamSpider)
for p in process.crawlers:
    p.signals.connect(collect, signal=scrapy.signals.item_scraped)
process.start()

result.sort()
print('RES:', result, len(result))
