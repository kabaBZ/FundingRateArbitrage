import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from Clients.bybit_client import BybitTimeRecordClient
from config import BYBIT_API_KEY, BYBIT_API_SECRET, MINIMAL_ACCEPTABLE_FUNDING_RATE
from single_direction_trade.abstract_base import SingleDirectionTrade
from tools.customer_loger import logger
from tools.utils import format_num_by_step, supported_arbitrage_timing_dict


class BybitSingleDirectionTrade(SingleDirectionTrade):
    """
    bybit单向资金费率套利
    没有反向杠杆交易对的限制，机会较多，风险较大
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        balance_ratio: 资金比例 默认全仓 一半就传0.5
        """
        super().__init__(*args, **kwargs)
        demo = kwargs.get("demo", True)
        self.client = BybitTimeRecordClient(
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET,
            demo=demo,  # 设置为True使用测试网络
        )

    def get_server_time(self) -> Optional[datetime]:
        """获取Bybit服务器时间"""
        try:
            time_response = self.client.get_server_time()
            if time_response.get("retCode") == 0:
                current_server_time = datetime.fromtimestamp(
                    int(time_response["result"]["timeNano"]) / 1000000000
                )
                self.logger.info(f"当前服务器时间：{current_server_time}")
                return current_server_time
        except Exception as e:
            self.logger.info(f"获取服务器时间失败: {str(e)}")
        return None

    # def get_upcoming_timing_from_preset(self, current_hour):
    #     """从预设的时间点中获取最近的时间点"""
    #     for hour, time_tuple in supported_arbitrage_timing_dict.items():
    #         if hour > current_hour:
    #             return time_tuple

    # def get_upcoming_timing_from_user_config(self, current_hour):
    #     """从预设的时间点中获取最近的时间点"""
    #     for hour, time_tuple in supported_arbitrage_timing_dict.items():
    #         if hour >= current_hour and hour in self.timingPoints:
    #             return time_tuple

    # def get_upcoming_time_tuple(self, server_time):
    #     """获取最近的时间点,并转化为时间tuple"""
    #     if not self.timingPoints:
    #         self.logger.info("未设置时间点，使用默认时间点")
    #         return self.get_upcoming_timing_from_preset(server_time.hour)
    #     else:
    #         time_tuple = self.get_upcoming_timing_from_user_config(server_time.hour)
    #         if not time_tuple:
    #             self.logger.info("用户配置无效，使用默认时间点")
    #             return self.get_upcoming_timing_from_preset(server_time.hour)
    #         else:
    #             return time_tuple

    # def parse_promising_arbitrage_time(self, time_tuple):
    #     hour = time_tuple[0]
    #     minute = time_tuple[1]
    #     second = time_tuple[2]
    #     # 预期清算时间
    #     trade_time = datetime.now().replace(
    #         hour=hour, minute=minute, second=second, microsecond=0
    #     )
    #     # 零点日期改为明天
    #     if hour == 0:
    #         target_close_time = trade_time + timedelta(days=1)
    #     return trade_time

    def wait_until_place_linear_arbitrage_order(
        self,
        target_open_time,
        target_close_time,
        promising_arbitrage_time,
        qty_step,
        max_order_qty,
        min_order_qty,
        leverage,
        amount,
    ):
        """
        倒计时等待下合约套利单
        """
        # 等待开仓时间
        self.logger.info(f"等待开仓时间: {target_open_time}")
        self.wait_until(target_open_time)

        # 获取当前价格
        ticker = self.client.get_tickers(category="linear", symbol=self.symbol)
        current_price = Decimal(ticker["result"]["list"][0]["lastPrice"])

        # 获取合约数量相关参数
        # 计算基于余额和杠杆的最大可开仓数量（以合约数量为单位）
        max_position_value = Decimal(amount) * Decimal(leverage)  # 最大持仓价值
        qty = max_position_value / Decimal(current_price)  # 转换为合约数量

        # 确保数量符合步长要求并不超过最大下单限制
        qty = format_num_by_step(qty, qty_step)  # 按步长格式化
        qty = max(
            min_order_qty, min(qty, max_order_qty)
        )  # 确保在最小和最大下单限制之间
        # 最终确定下单数量
        finalQTY = qty
        fundingRate = Decimal(ticker["result"]["list"][0]["fundingRate"])
        self.logger.info(f"当前资金费率: {fundingRate}")
        enclosure_time = datetime.fromtimestamp(
            int(ticker["result"]["list"][0]["nextFundingTime"]) / 1000
        )
        self.logger.info(f"本次结算时间(ms): {enclosure_time}")
        if fundingRate >= Decimal(0):
            # 正税率暂不支持
            self.logger.info("暂不支持正税率套利")
            return
        elif fundingRate > Decimal(MINIMAL_ACCEPTABLE_FUNDING_RATE):
            # 负税率但收益低
            self.logger.info("资金费率过低，停止此次套利")
            return

        # 开仓
        open_order = self.client.place_order(
            category="linear",
            symbol=self.symbol,
            side="Buy",
            order_type="Market",
            qty=finalQTY,
            reduce_only=False,
        )
        self.logger.info(
            f"{self.symbol}开仓成功: {open_order}, 订单时间：{datetime.fromtimestamp(open_order['time'] / 1000)}"
        )
        if promising_arbitrage_time < datetime.fromtimestamp(open_order["time"] / 1000):
            self.logger.info(
                f"{self.symbol}开仓时间晚于预期结算时间, 可能是网络延迟导致的, 预期套利失败"
            )
        else:
            self.logger.info(f"{self.symbol}开仓时间早于预期结算时间, 预期套利成功")

        # 等待平仓时间
        self.logger.info(f"等待平仓时间: {target_close_time}")
        self.wait_until(target_close_time)

        # 平仓
        close_order = self.client.place_order(
            category="linear",
            symbol=self.symbol,
            side="Sell",
            order_type="Market",
            qty=finalQTY,
            reduce_only=True,
        )
        self.logger.info(
            f"{self.symbol}平仓成功: {close_order}, 订单时间：{datetime.fromtimestamp(close_order['time'] / 1000)}"
        )
        if promising_arbitrage_time > datetime.fromtimestamp(
            close_order["time"] / 1000
        ):
            self.logger.info(
                f"{self.symbol}平仓时间早于预期结算时间, 可能是网络延迟导致的, 预期套利失败"
            )
        else:
            self.logger.info(f"{self.symbol}平仓时间晚于预期结算时间, 预期套利成功")

    def workflow(self):
        # 设置目标时间
        server_time = self.get_server_time()
        if not server_time:
            raise Exception("无法获取服务器时间")
        ticker = self.client.get_tickers(category="linear", symbol=self.symbol)
        # 获取结算时间
        enclosure_time = datetime.fromtimestamp(
            int(ticker["result"]["list"][0]["nextFundingTime"]) / 1000
        )
        promising_arbitrage_time = enclosure_time
        fundingRate = Decimal(ticker["result"]["list"][0]["fundingRate"])
        self.logger.info(f"下次结算时间: {enclosure_time}")
        self.logger.info(f"下次结算费率: {fundingRate}")
        if fundingRate >= Decimal(0):
            # 正税率暂不支持
            self.logger.info("暂不支持正税率套利")
            return
        elif fundingRate > Decimal(MINIMAL_ACCEPTABLE_FUNDING_RATE):
            # 负税率但收益低
            self.logger.info("资金费率过低，停止此次套利")
            return

        ### 开始准备套利

        # 获取开平仓时间
        target_open_time, target_close_time = self.get_trade_time(
            server_time=server_time, promising_arbitrage_time=promising_arbitrage_time
        )
        # 获取交易对信息
        instrument_info = self.client.get_instruments_info(
            category="linear", symbol=self.symbol
        )["result"]["list"][0]
        # 数量步长
        qty_step = Decimal(instrument_info["lotSizeFilter"]["qtyStep"])
        # 最大下单数量
        max_order_qty = Decimal(instrument_info["lotSizeFilter"]["maxMktOrderQty"])
        # 最小下单数量
        min_order_qty = Decimal(
            instrument_info["lotSizeFilter"].get("minOrderQty", qty_step)
        )
        # 获取杠杆信息
        max_leverage = Decimal(instrument_info["leverageFilter"]["maxLeverage"])
        leverage = Decimal("50") if max_leverage > Decimal("50") else max_leverage
        # 获取当前余额
        current_balance = self.client.get_wallet_balance(
            accountType="UNIFIED", coin="USDT"
        )
        current_balance = Decimal(
            current_balance["result"]["list"][0]["totalAvailableBalance"]
        ) * Decimal(self.balance_ratio)
        # 预留3%的余额作为缓冲，避免因手续费和滑点导致开仓失败
        buffer_ratio = Decimal("0.97")
        amount = (
            current_balance * buffer_ratio / 2
        )  # 合约和现货杠杆的保证金金额，除以2实现对冲

        # 设置合约端杠杆
        try:
            self.client.set_leverage(
                category="linear",
                symbol=self.symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage),
            )
        except Exception as e:
            if "leverage not modified" in str(e):
                # 已经设置过相同杠杆，再次设置就会报错
                pass

        self.wait_until_place_linear_arbitrage_order(
            target_open_time,
            target_close_time,
            promising_arbitrage_time,
            qty_step,
            max_order_qty,
            min_order_qty,
            leverage,
            amount,
        )


def run(*args, **kwargs) -> None:
    client = BybitSingleDirectionTrade(*args, **kwargs)
    client.workflow()
