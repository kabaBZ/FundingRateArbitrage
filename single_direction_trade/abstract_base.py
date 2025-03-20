import time
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from Clients.bybit_client import BybitTimeRecordClient


class SingleDirectionTrade(object):
    def __init__(
        self,
        symbol: str,
        timingPoints: Optional[tuple] = None,
        balance_ratio=1,
        demo: bool = True,
        debug_mode: bool = False,
        logger=logger,
    ) -> None:
        """
        balance_ratio: 资金比例 默认全仓 一半就传0.5
        """
        self.logger = logger
        self.debug_mode = debug_mode
        self.symbol = symbol
        self.timingPoints = timingPoints
        self.balance_ratio = balance_ratio
        self.client: Optional[BybitTimeRecordClient] = None

    def get_trade_time(
        self, server_time, promising_arbitrage_time
    ) -> tuple([datetime]):
        """获取开仓时间和平仓时间"""
        trade_time = promising_arbitrage_time
        # 提前1.8秒建仓，防止网慢吃不到结算
        target_open_time = trade_time + timedelta(seconds=-1, microseconds=-800000)
        # 结算点直接平仓
        target_close_time = trade_time
        return target_open_time, target_close_time

    def wait_until(self, target_time: datetime):
        """等待直到目标时间，使用服务器时间"""
        if self.debug_mode:
            print("debug模式下不等待")
            return
        while True:
            server_time = self.get_server_time()
            if not server_time:
                time.sleep(0.3)
                continue
            if (
                target_time - server_time
            ).total_seconds() <= self.client.get_average_response_time() / 1000000:
                print(f"等待结束，服务器时间：{server_time}")
                break
            # 计算等待时间
            wait_seconds = (target_time - server_time).total_seconds()
            if wait_seconds > 6:
                time.sleep(5)  # 长等待时间，每5秒同步一次
            else:
                time.sleep(0.01)  # 接近目标时间，更频繁地同步

    @abstractmethod
    def get_server_time(self) -> Optional[datetime]: ...
