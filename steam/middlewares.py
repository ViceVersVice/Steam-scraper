# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware

class SteamSpiderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, dict or Item objects.
        print('OUT', response.request._meta)
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request, dict
        # or Item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            if spider.scrape_runner.rotate_proxy:
                spider.scrape_runner.rotate_proxy = False
                try:
                    r._meta = {'proxy': spider.scrape_runner.proxy_generator.__next__()}
                except StopIteration:
                    spider.scrape_runner.restore_generator()
                    r._meta = {'proxy': spider.scrape_runner.proxy_generator.__next__()}
            elif r._meta is None:
                r._meta = {'proxy': spider.scrape_runner.active_proxy}
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class SteamDownloaderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        if response.status in [403, 429] or not request._meta.get('proxy'):
            print('-----429/430')
            spider.scrape_runner.rotate_proxy = True
        else:
            # If we get good request --> use same proxy for next iteration in crawl loop
            spider.scrape_runner.active_proxy = request._meta.get('proxy')
            spider.scrape_runner.rotate_proxy = False
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class PriceMonitorRetryMiddleware(RetryMiddleware):
    def process_exception(self, request, exception, spider):
        print('EXCEP', exception.__class__,  request._meta.get('proxy'), request._meta.get('retry_times'))
        if isinstance(exception, self.EXCEPTIONS_TO_RETRY) and request._meta.get('retry_times') == self.max_retry_times:
            print('TIMEOUT --> ROTATE')
            spider.scrape_runner.rotate_proxy = True
        # return super().process_exception(request, exception, spider)