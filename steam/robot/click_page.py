import json
import math
import pprint
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

pp = pprint.PrettyPrinter(indent=4)


class StatusException(Exception):
    pass


def add_cookies_(driver, refresh=False):
    with open('/home/botadd/PycharmProjects/SS/steam/steam/robot/cookies.json', 'r') as file_:
        for cook in json.loads(file_.read()):
            # For login this parameter should be excluded
            if refresh and cook.get('name') == 'steamLoginSecure':
                continue
            driver.add_cookie({'name': cook['name'], 'value': cook['value'], 'domain': 'steamcommunity.com'})


def make_login():
    # TODO obtained after login cookies don`t work
    url = 'https://steamcommunity.com/login/home/?goto='
    with open('login_data.json', 'r') as f:
        data = json.loads(f.read())
        username = data['username']
        password = data['password']

    driver = webdriver.Firefox()
    driver.get(url)  # Initiate browsing content

    # Initiate cookies for be detected as same user and login without sms/email
    add_cookies_(driver, refresh=True)
    driver.get(url)
    time.sleep(1)

    login_form = driver.find_element_by_id('loginForm')
    login_form.find_element_by_xpath('.//input[@id="steamAccountName"]').send_keys(username)
    login_form.find_element_by_xpath('.//input[@id="steamPassword"]').send_keys(password)
    login_form.find_element_by_xpath('.//input[@id="SteamLogin"]').click()
    time.sleep(0.5)
    driver.refresh()
    cookies = driver.get_cookies()

    driver.close()
    # Update cookies
    with open('/home/botadd/PycharmProjects/SS/steam/steam/robot/cookies.json', 'w+') as file_:
        file_.write(json.dumps(cookies))



def find_and_buy(element_id, url):
    element_id_id = f'listing_{element_id}'
    driver = webdriver.Firefox()
    driver.get(url)
    add_cookies_(driver)
    driver.get(url)
    max_tries = 10
    time.sleep(1)

    for i in range(max_tries):
        try:
            class_name = f'market_listing_row market_recent_listing_row listing_{element_id}'
            item_main_class = driver.find_element_by_xpath(f'//div[@id="{element_id_id}" and @class="{class_name}"]')
            buy_button = item_main_class.find_element_by_xpath('.//div[@class="market_listing_buy_button"]')
            print(f'FOUND ON {i}', buy_button)
            buy_button.click()
            for _ in range(3):
                try:
                    agreement_checkbox = driver.find_element_by_xpath(f'//input[@id="market_buynow_dialog_accept_ssa"]')
                    agreement_checkbox.click()
                    break
                except Exception as e:
                    time.sleep(0.5)
                    continue
            else:
                driver.close()
                raise StatusException('FAIL TO SIGN AGREEMENT')

            for _ in range(3):
                try:
                    purchase_link = driver.find_element_by_xpath(f'//a[@id="market_buynow_dialog_purchase"]')
                    purchase_link.click()
                    driver.close()
                    return 'BOUGHT'
                except Exception as e:
                    time.sleep(0.2)
                    continue
            driver.close()
            raise StatusException('FAIL TO BUY')
        except Exception:
            next_page = driver.find_element_by_id('searchResults_btn_next')
            next_page.click()
    driver.close()
    raise StatusException('FAIL TO FIND ITEM BY ID')


def sell(inventory_url, item_name, bought_price):
    # As after buying item identifier is lost, we assume that it will appear as first one item in inventory
    driver = webdriver.Firefox()

    for _ in range(2):
        try:
            driver.get(inventory_url)
            add_cookies_(driver)
            driver.refresh()
            sell_button = driver.find_element_by_xpath(f'//a[contains(@class, "item_market_action_button")]')
            time.sleep(1)
            sell_button.click()
            break
        except Exception:
            # make_login()
            time.sleep(0.5)
    else:
        driver.close()
        raise StatusException('FAIL TO FIND SELL BUTTON')

    for _ in range(2):
        try:
            item_name_for_sell = driver.find_element_by_xpath(f'//div[@id="market_sell_dialog_item_name"]').text
            if item_name_for_sell == item_name:
                sell_price_input = driver.find_element_by_xpath(f'//input[@id="market_sell_currency_input"]')
                break
        except Exception:
            time.sleep(0.5)
    else:
        driver.close()
        raise StatusException('FAIL TO FIND SELL PRICE INPUT')

    for _ in range(2):
        try:
            agreement_checkbox = driver.find_element_by_xpath(f'//input[@id="market_sell_dialog_accept_ssa"]')
            agreement_checkbox.click()
            break
        except Exception:
            time.sleep(0.5)
    else:
        driver.close()
        raise StatusException('FAIL TO FIND/SELECT AGREEMENT SELL CHECKBOX')

    sell_price = math.ceil(bought_price * 1.05) * 0.01
    for _ in range(2):
        try:
            sell_price_input.send_keys(str(sell_price))
            put_for_sell_button = driver.find_element_by_xpath(f'//a[@id="market_sell_dialog_accept"]')
            put_for_sell_button.click()
            ok_button = driver.find_element_by_xpath(f'//a[@id="market_sell_dialog_ok"]')
            time.sleep(1)
            ok_button.click()
            driver.close()
            return f'SOLD {item_name} for {sell_price}'
        except Exception:
            time.sleep(1)
    else:
        driver.close()
        raise StatusException('FAIL TO SELL LAST STEP')
