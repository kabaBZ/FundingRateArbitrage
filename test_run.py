import sys

from single_direction_trade.bybit import run
from tools.customer_loger import logger
from loguru import _defaults

if __name__ == "__main__":
    # run("MAVIAUSDT", debug_mode=True)
    # from datetime import datetime
    # import time

    # print(time.time())
    # print(datetime.fromtimestamp(time.time()))
    # print(f"{datetime.fromtimestamp(1742353649780 / 1000)}")

    # 多币种套利
    import threading
    from threading import Thread

    default_format = _defaults.LOGURU_FORMAT
    customer_format = (
        default_format.split(" - <level>")[0]
        + "   {extra[name]}"
        + " - <level>"
        + default_format.split(" - <level>")[1]
    )

    logger.add(sys.stdout, format=customer_format)

    symbols = ["MAVIAUSDT", "API3USDT", "RSS3USDT", "DYMUSDT", "VIDTUSDT"]  #
    threads = []
    for symbol in symbols:
        logger.add(
            f"./logs/{symbol}_BybitSingleDirectionTrade.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[name]} | {level} | {name}:{function}:{line} - {message}",
            filter=lambda record: record["extra"]["name"] == symbol,
            rotation="200KB",
        )
        thread = threading.Thread(
            target=run,
            args=(symbol,),
            kwargs={
                "balance_ratio": 1 / len(symbols),
                "logger": logger.bind(
                    name=symbol,
                ),
            },
        )
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
