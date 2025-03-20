from pybit.unified_trading import HTTP
from datetime import datetime, timedelta
from collections import deque
from typing import Optional


class BybitTimeRecordClient(HTTP):
    def __init__(self, *args, **kwargs):
        logger = kwargs.pop("logger")
        super().__init__(*args, **kwargs)
        self.logger = logger
        self.response_time_records = deque(maxlen=15)
        self.record_request_time = True
        self.retry_delay = 0.1

    def get_average_response_time(self):
        return (
            sum(self.response_time_records) / len(self.response_time_records)
            if self.response_time_records
            else 0
        )

    def get_server_time(self):
        """获取Bybit服务器时间"""
        if not self.record_request_time:
            return super().get_server_time()
        time_response = super().get_server_time()
        self.logger.info(f"get_server_time请求耗时：{time_response[1].microseconds}")
        self.response_time_records.append(time_response[1].microseconds)
        time_response = time_response[0]
        return time_response

    def get_instruments_info(self, *args, **kwargs):
        """获取Bybit服务器时间"""
        if not self.record_request_time:
            return super().get_instruments_info(*args, **kwargs)
        instruments_response = super().get_instruments_info(*args, **kwargs)
        self.logger.info(
            f"get_instruments_info请求耗时：{instruments_response[1].microseconds}"
        )
        self.response_time_records.append(instruments_response[1].microseconds)
        instruments_response = instruments_response[0]
        return instruments_response

    def get_wallet_balance(self, *args, **kwargs):
        """获取钱包余额"""
        if not self.record_request_time:
            return super().get_wallet_balance(*args, **kwargs)
        wallet_balance_response = super().get_wallet_balance(*args, **kwargs)
        self.logger.info(
            f"get_wallet_balance请求耗时：{wallet_balance_response[1].microseconds}"
        )
        self.response_time_records.append(wallet_balance_response[1].microseconds)
        wallet_balance_response = wallet_balance_response[0]
        return wallet_balance_response

    def get_tickers(self, *args, **kwargs):
        """获取最新价格"""
        if not self.record_request_time:
            return super().get_tickers(*args, **kwargs)
        tickers_response = super().get_tickers(*args, **kwargs)
        self.logger.info(f"get_tickers请求耗时：{tickers_response[1].microseconds}")
        self.response_time_records.append(tickers_response[1].microseconds)
        tickers_response = tickers_response[0]
        return tickers_response

    def place_order(self, *args, **kwargs):
        """下单"""
        if not self.record_request_time:
            return super().place_order(*args, **kwargs)
        place_order_response = super().place_order(*args, **kwargs)
        self.logger.info(f"place_order请求耗时：{place_order_response[1].microseconds}")
        self.response_time_records.append(place_order_response[1].microseconds)
        place_order_response = place_order_response[0]
        return place_order_response
