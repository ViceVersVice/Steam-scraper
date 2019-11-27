import statistics
from _queue import Empty

from steam.robot.click_page import find_and_buy, sell
from twisted.internet import reactor
from twisted.internet.task import deferLater

from steam.robot.click_page import StatusException


class CallBacks:
    SUCCESS = 1
    FAIL = 2

    prices_list = []
    log_file = '/home/botadd/PycharmProjects/SS/steam/steam/spiders/scrape_log.txt'

    @staticmethod
    def _sleep(obj, seconds, *args, **kwargs):
        return deferLater(reactor, seconds, lambda: None)

    @staticmethod
    def collect_prices(item, response, spider):
        CallBacks.prices_list.extend(item['prices'])

    @staticmethod
    def estimate_mediana(*args, **kwargs):
        print('lennnnth', len(CallBacks.prices_list))
        print('MEDIANA:::', statistics.median(CallBacks.prices_list))

    @staticmethod
    def perform_buy(item_id, min_price, med_price, items_listing_url):
        with open(CallBacks.log_file, 'a+') as ff:
            ff.write('---------------------------------------------- \n')
            ff.write(f'YEAS: {min_price}, {med_price} {item_id}\n')
            try:
                status = find_and_buy(item_id, items_listing_url)
                if status:
                    ff.write(f'STATUS: {str(status)}:{item_id} \n')
                    return CallBacks.SUCCESS
            except StatusException as e:
                ff.write(f'FAIL TO BOUGHT {item_id}, ERR: {str(e)} \n')
            except Exception as e:
                ff.write(f'UNEXPECTED EXCEPTION {item_id}, ERR: {str(e)} \n')

        return CallBacks.FAIL

    @staticmethod
    def perform_sell(item_id, item_name, min_price, inventory_url):
        with open(CallBacks.log_file, 'a+') as ff:
            try:
                status = sell(inventory_url, item_name, min_price)
                if status:
                    ff.write(f'STATUS: {str(status)}:{item_id} \n')
                    return CallBacks.SUCCESS
            except StatusException as e:
                ff.write(f'FAIL TO SELL {item_name}:{item_id}, ERR: {str(e)} \n')
            except Exception as e:
                ff.write(f'UNEXPECTED EXCEPTION {item_id}, ERR: {str(e)} \n')

        return CallBacks.FAIL

    @staticmethod
    def buy_and_sell(result, queue):
        while True:
            try:
                q = queue.get(block=False)
            except Empty:
                return

            if q is not None:
                with open(CallBacks.log_file, 'a+') as ff:
                    try:
                        item_info = f'{q["item_name"]}:{q["item_id"]}'
                        buy_status = CallBacks.perform_buy(q['item_id'], q['min_price'], q['med_price'], q['items_listing_url'])
                        if buy_status == CallBacks.SUCCESS:
                            ff.write(f'----SUCCSESS BOUGHT---- {item_info} \n')

                            sell_status = CallBacks.perform_sell(q['item_id'], q['item_name'], q['min_price'], q['inventory_url'])
                            if sell_status == CallBacks.SUCCESS:
                                ff.write(f'----SUCCSESS SOLD---- {item_info} \n')
                            else:
                                ff.write(f'----FAIL TO SOLD---- {item_info} \n')
                        else:
                            ff.write(f'----FAIL TO BUY---- {item_info} \n')
                    except Exception as e:
                        ff.write(f'UNEXPECTED ERR IN buy_and_sell {item_info}: {str(e)} \n')