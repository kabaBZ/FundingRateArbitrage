import sys
import copy
from single_direction_trade.bybit import run
from tools.customer_loger import logger
from loguru import _defaults
import threading
from threading import Thread
import time

if __name__ == "__main__":
    default_format = _defaults.LOGURU_FORMAT
    customer_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>| <level>{level:<8}</level>| <cyan>{function}</cyan>:<cyan>{line}</cyan>-{extra[name]} <level>{message}</level>"

    logger.add(sys.stdout, format=customer_format)
    # 单币种
    # run("API3USDT", debug_mode=False, demo=False, logger=logger.bind(
    #                 name="GEMSUSDT",
    #             ))

    # 多币种套利
    symbols = [
        # "MAVIAUSDT",
        # "API3USDT",
        "VIDTUSDT",
        # "GEMSUSDT",
        # "RSS3USDT",
        # "DYMUSDT",
        # "VANAUSDT",
        "AUCTIONUSDT"
    ]  #
    threads = []
    for symbol in symbols:
        # 为每个 symbol 创建一个过滤器函数
        def make_filter(s):
            return lambda record: record["extra"]["name"] == s

        logger.add(
            f"./logs/{symbol}_BybitSingleDirectionTrade.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[name]} | {level} | {function}:{line} - {message}",
            filter=make_filter(symbol),
            rotation="200MB",
        )
        # 创建一个新的 logger 实例并绑定当前的 symbol
        symbol_logger = logger.bind(name=symbol)
        thread = threading.Thread(
            target=run,
            args=(symbol,),
            kwargs={
                "balance_ratio": 1 / len(symbols),
                "logger": symbol_logger,
                "demo": False,
            },
        )
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
