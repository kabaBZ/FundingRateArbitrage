import time
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from config import BYBIT_API_KEY, BYBIT_API_SECRET
import math
from decimal import Decimal as decimal
from collections import deque

# 初始化Bybit API客户端
client = HTTP(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
    demo=True,  # 设置为True使用测试网络
)
client.record_request_time = True
client.retry_delay = 0.1
response_time_records = deque(maxlen=10)


def format_num_by_step(num, step):
    """根据步长格式化数字"""
    return decimal(int(decimal(num) / decimal(step))) * decimal(step)


def get_server_time():
    """获取Bybit服务器时间"""
    try:
        time_response = client.get_server_time()
        print(f"请求耗时：{time_response[1].microseconds}")
        response_time_records.append(time_response[1].microseconds)
        time_response = time_response[0]
        if time_response.get("retCode") == 0:
            # print(f'本地时间与服务器差值：{int(time.time())}-{int(time_response["result"]["timeSecond"])}={int(time.time()) - int(time_response["result"]["timeSecond"])}秒')
            return datetime.fromtimestamp(time_response["result"]["timeSecond"])
    except Exception as e:
        print(f"获取服务器时间失败: {str(e)}")
    return None


def wait_until(target_time):
    """等待直到目标时间，使用服务器时间"""
    while True:
        server_time = get_server_time()
        if not server_time:
            time.sleep(1)
            continue

        if server_time >= target_time:
            break

        # 计算等待时间
        wait_seconds = (target_time - server_time).total_seconds()
        if wait_seconds > 5:
            time.sleep(5)  # 长等待时间，每5秒同步一次
        else:
            time.sleep(0.1)  # 接近目标时间，更频繁地同步


def main(symbol, time_tuple, seperate_into=1):
    try:
        # 设置目标时间
        server_time = get_server_time()
        if not server_time:
            raise Exception("无法获取服务器时间")

        # tomorrow = (
        #     server_time + timedelta(days=1) if server_time.hour >= 8 else server_time
        # )
        hour = time_tuple[0][0]
        minute = time_tuple[0][1]
        second = time_tuple[0][2]
        target_hour = time_tuple[1][0]
        target_minute = time_tuple[1][1]
        target_second = time_tuple[1][2]
        target_open_time = server_time.replace(
            hour=hour, minute=minute, second=second - 1, microsecond=0
        )
        target_close_time = server_time.replace(
            hour=target_hour,
            minute=target_minute,
            second=target_second,
            microsecond=500000,
        )
        if target_hour == 0:
            tomorrow = server_time + timedelta(days=1)
            target_close_time = tomorrow.replace(
                hour=target_hour,
                minute=target_minute,
                second=target_second,
                microsecond=100,
            )

        instrument_info = client.get_instruments_info(category="linear", symbol=symbol)[
            "result"
        ]["list"][0]
        print(f"请求耗时：{instrument_info[1].microseconds}")
        response_time_records.append(instrument_info[1].microseconds)
        instrument_info = instrument_info[0]
        max_leverage = decimal(instrument_info["leverageFilter"]["maxLeverage"])
        leverage = decimal("50") if max_leverage > decimal("50") else max_leverage

        current_balance = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        print(f"请求耗时：{current_balance[1].microseconds}")
        response_time_records.append(current_balance[1].microseconds)
        current_balance = current_balance[0]
        current_balance = decimal(
            current_balance["result"]["list"][0]["totalAvailableBalance"]
        ) / decimal(seperate_into)
        # 预留5%的余额作为缓冲，避免因手续费和滑点导致开仓失败
        buffer_ratio = decimal("0.95")
        amount = current_balance * buffer_ratio

        # 设置合约端杠杆
        try:
            client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage),
            )
        except Exception as e:
            if "leverage not modified" in str(e):
                # 已经设置过2倍杠杆，再次设置就会报错
                pass

        # 等待开仓时间
        print(f"等待开仓时间: {target_open_time}")
        wait_until(target_open_time)

        # 获取当前价格
        ticker = client.get_tickers(category="linear", symbol=symbol)
        print(f"请求耗时：{ticker[1].microseconds}")
        response_time_records.append(ticker[1].microseconds)
        ticker = ticker[0]
        current_price = decimal(ticker["result"]["list"][0]["lastPrice"])

        # 获取合约数量相关参数
        qty_step = decimal(instrument_info["lotSizeFilter"]["qtyStep"])  # 数量步长
        max_order_qty = decimal(
            instrument_info["lotSizeFilter"]["maxMktOrderQty"]
        )  # 最大下单数量
        min_order_qty = decimal(
            instrument_info["lotSizeFilter"].get("minOrderQty", qty_step)
        )  # 最小下单数量

        # 计算基于余额和杠杆的最大可开仓数量（以合约数量为单位）
        max_position_value = decimal(amount) * decimal(leverage)  # 最大持仓价值
        qty = max_position_value / decimal(current_price)  # 转换为合约数量

        # 确保数量符合步长要求并不超过最大下单限制
        qty = format_num_by_step(qty, qty_step)  # 按步长格式化
        qty = max(
            min_order_qty, min(qty, max_order_qty)
        )  # 确保在最小和最大下单限制之间

        # 最终确定下单数量
        finalQTY = qty

        # 开仓
        open_order = client.place_order(
            category="linear",
            symbol=symbol,
            side="Buy",
            order_type="Market",
            qty=finalQTY,
            reduce_only=False,
            price=current_price,
        )
        print(f"开仓成功: {open_order}")

        # 等待平仓时间
        print(f"等待平仓时间: {target_close_time}")
        wait_until(target_close_time)

        # 平仓
        close_order = client.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            order_type="Market",
            qty=finalQTY,
            reduce_only=True,
        )
        print(f"平仓成功: {close_order}")
    except Exception as e:
        print(f"交易执行错误: {str(e)}")


if __name__ == "__main__":
    main("AERGOUSDT", ((1, 6, 59), (1, 7, 1)))
    # main("AERGOUSDT", ((23, 59, 59), (0, 0, 0)))
    # main(((7, 59, 59), (8, 0, 1)))
    # from threading import Thread
    # Thread.daemon = True
    # import threading
    # symbols = ["MAVIAUSDT"]
    # threads = []
    # for symbol in symbols:
    #     seperate = len(symbols)
    #     for time_tuple in [((7, 59, 59), (8, 0, 0))]:
    #         thread = threading.Thread(target=main, args=(symbol, time_tuple, seperate))
    #         thread.start()
    #         threads.append(thread)
    # for thread in threads:
    #     thread.join()
