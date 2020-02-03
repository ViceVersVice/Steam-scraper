import time

import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys

from steam.steam.robot.click_page import add_cookies_


class FindProfitableItems:
    items_query_url_part = '/render/?query=&start={start}&count={count}&country=US&language=english&currency=1'

    def __init__(self):
        self.driver = webdriver.Firefox()
        self.url = 'https://steamcommunity.com/market/search?q=&category_730_ItemSet%5B%5D=any&category_730_ProPlayer%5B%5D=any&category_730_StickerCapsule%5B%5D=any&category_730_TournamentTeam%5B%5D=any&category_730_Weapon%5B%5D=any&category_730_Exterior%5B%5D=tag_WearCategory2&category_730_Exterior%5B%5D=tag_WearCategory1&category_730_Exterior%5B%5D=tag_WearCategory4&category_730_Exterior%5B%5D=tag_WearCategory3&category_730_Exterior%5B%5D=tag_WearCategory0&category_730_Exterior%5B%5D=tag_WearCategoryNA&appid=730'

    def go_next_page(self):
        next_page = self.driver.find_element_by_id('searchResults_btn_next')
        next_page.click()

    def get_minimum_price(self):
        min_buy_orders = self.driver.find_element_by_xpath('//div[@id="market_commodity_buyrequests"]')
        # Need to sleep
        time.sleep(1.5)
        if min_buy_orders.text:
            # Beautiful
            min_buy_price = float([e for e in min_buy_orders.text.split() if e.startswith('$')][0].split('$')[1])
            return min_buy_price
        else:
            raise Exception('LOL1')

    def get_query_url(self):
        self.query_url = self.driver.current_url + self.items_query_url_part.format(start=0, count=20)

    def get_medium_price(self, count=20):
        response = requests.get(self.query_url)
        json_response = response.json()
        items = list(json_response['listinginfo'].values())
        prices_sum = sum([item['converted_price_per_unit'] + item['converted_fee_per_unit'] for item in items])
        medium_price = round(prices_sum / (len(items) * 100), 2)
        return medium_price

    def check_passed(self, item):
        quantity_element = item.find_element_by_class_name('market_listing_num_listings_qty')
        quantity = int(''.join(quantity_element.text.split(',')))
        if quantity > 150:
            return True

    def compare_prices(self):
        self.get_query_url()
        minimum_price = self.get_minimum_price()
        print('MIN PRICE', minimum_price)
        medium_price = self.get_medium_price()
        print('MED', medium_price)
        if minimum_price > 0.1:
            if (minimum_price * 1.15) + 0.01 < medium_price:
                with open('res.txt', 'a') as f:
                    f.write(self.query_url + '\n')

    def run(self):
        # self.driver.get(self.url)
        # add_cookies_(self.driver)
        self.driver.get(self.url)
        self.next_ = False
        while True:
            main_window = self.driver.current_window_handle
            for n in range(10):
                self.driver.switch_to.window(main_window)
                try:
                    items = self.driver.find_elements_by_css_selector('a[class="market_listing_row_link"]')
                    item = items[n]
                    if not self.check_passed(item):
                        continue
                    item.send_keys(Keys.CONTROL + Keys.ENTER)
                    time.sleep(2)
                    self.driver.switch_to.window(self.driver.window_handles[1])
                    self.compare_prices()
                    self.driver.close()
                    break
                except Exception as e:
                    print(e)
                    if self.driver.current_window_handle != main_window:
                        print(self.driver.current_window_handle, main_window)
                        self.driver.close()
                    time.sleep(60)
                    self.driver.switch_to.window(main_window)
                    self.driver.refresh()
                    break
            else:
                try:
                    self.driver.switch_to.window(main_window)
                    self.go_next_page()
                except NoSuchElementException:
                    self.driver.refresh()
                    continue

FindProfitableItems().run()