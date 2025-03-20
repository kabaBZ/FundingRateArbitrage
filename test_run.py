import sys

from single_direction_trade.bybit import run
from tools.customer_loger import logger
from loguru import _defaults
import threading
from threading import Thread
import time

if __name__ == "__main__":
    default_format = _defaults.LOGURU_FORMAT
    customer_format = (
        default_format.split(" - <level>")[0]
        + "   {extra[name]}"
        + " - <level>"
        + default_format.split(" - <level>")[1]
    )

    logger.add(sys.stdout, format=customer_format)
    # 单币种
    # run("API3USDT", debug_mode=False, demo=False, logger=logger.bind(
    #                 name="GEMSUSDT",
    #             ))

    # 多币种套利
    while True:
        symbols = ["MAVIAUSDT", "API3USDT", "VIDTUSDT", "GEMSUSDT", "RSS3USDT", "DYMUSDT"]  # 
        threads = []
        for symbol in symbols:
            logger.add(
                f"./logs/{symbol}_BybitSingleDirectionTrade.log",
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[name]} | {level} | {name}:{function}:{line} - {message}",
                filter=lambda record: record["extra"]["name"] == symbol,
                rotation="200MB",
            )
            thread = threading.Thread(
                target=run,
                args=(symbol,),
                kwargs={
                    "balance_ratio": 1 / len(symbols),
                    "logger": logger.bind(
                        name=symbol,
                    ),
                    "demo": False
                },
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
