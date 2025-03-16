import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pybit.unified_trading import HTTP
from ArbitrageData.arbitrage_list import get_interestArbitrage_data

# 资金费率套利策略类
# 通过在合约和现货市场同时开立反向仓位，利用资金费率差异获取收益
# 主要逻辑：
# 1. 监控Bybit交易所的资金费率
# 2. 当资金费率超过阈值时，在合约和现货市场开立反向仓位
# 3. 在资金费率结算前平仓，获取资金费率收益
class FundingRateArbitrage:
    def __init__(self, 
                 api_key: str,
                 api_secret: str,
                 demo: bool = False,
                 min_funding_rate: float = 0.001,  # 最小资金费率阈值
                 max_position_value: float = 1000,  # 单个币种最大持仓价值(USDT)
                 fee_rate: float = 0.0006,  # 交易手续费率
                 margin_interest_rate: float = 0.0002  # 每8小时杠杆利息率
                 ):
        """初始化资金费率套利策略
        Args:
            api_key: Bybit API密钥
            api_secret: Bybit API密钥
            test_net: 是否使用测试网络
            min_funding_rate: 最小资金费率阈值，低于此值不开仓
            max_position_value: 单个币种最大持仓价值(USDT)
            fee_rate: 交易手续费率
            margin_interest_rate: 每8小时杠杆利息率
        """
        # 初始化Bybit API客户端
        self.client = HTTP(
            demo=demo,
            api_key=api_key,
            api_secret=api_secret
        )
        # 设置策略参数
        self.min_funding_rate = min_funding_rate
        self.max_position_value = max_position_value
        self.fee_rate = fee_rate
        self.margin_interest_rate = margin_interest_rate
        # 记录当前持仓信息，格式：{symbol: {direction, amount, open_time}}
        self.positions: Dict[str, Dict] = {}

    def get_next_funding_time(self) -> datetime:
        """获取下一个资金费率结算时间"""
        now = datetime.utcnow()
        # Bybit资金费率结算时间为UTC 0:00, 8:00, 16:00
        hours = [0, 8, 16]
        next_hour = next(h for h in hours if h > now.hour % 24) if now.hour % 24 < 16 else hours[0]
        next_date = now.date() if next_hour > now.hour % 24 else now.date() + timedelta(days=1)
        return datetime.combine(next_date, datetime.min.time().replace(hour=next_hour))

    def calculate_profit(self, funding_rate: float, holding_hours: float) -> float:
        """计算预期收益率
        Args:
            funding_rate: 资金费率
            holding_hours: 持仓时间（小时）
        Returns:
            预期收益率
        """
        # 交易手续费成本（开仓+平仓）
        fee_cost = self.fee_rate * 2
        # 杠杆利息成本
        interest_cost = self.margin_interest_rate * (holding_hours / 8)
        # 总收益 = 资金费率收益 - 手续费成本 - 杠杆利息成本
        return funding_rate - fee_cost - interest_cost

    def find_arbitrage_opportunities(self) -> List[Dict]:
        """寻找套利机会
        通过分析当前市场资金费率，寻找符合条件的套利机会
        Returns:
            List[Dict]: 套利机会列表，按预期收益率排序
            每个机会包含：symbol(交易对), funding_rate(资金费率),
            expected_profit(预期收益率), direction(交易方向)
        """
        opportunities = []
        try:
            # 获取所有可交易的合约交易对
            linear_symbols = set()
            linear_instruments = self.client.get_instruments_info(
                category="linear",
                status="Trading"
            )
            if linear_instruments.get('retCode') == 0:
                for instrument in linear_instruments.get('result', {}).get('list', []):
                    linear_symbols.add(instrument.get('symbol'))

            # 获取所有可交易的现货交易对
            spot_symbols = set()
            spot_instruments = self.client.get_instruments_info(
                category="spot",
                status="Trading"
            )
            if spot_instruments.get('retCode') == 0:
                for instrument in spot_instruments.get('result', {}).get('list', []):
                    spot_symbols.add(instrument.get('symbol'))

            # 获取同时支持现货和合约交易的交易对
            available_symbols = linear_symbols.intersection(spot_symbols)

            # 获取所有交易对的资金费率数据
            data = get_interestArbitrage_data()
            # 计算持仓时间
            next_funding_time = self.get_next_funding_time()
            holding_hours = (next_funding_time - datetime.utcnow()).total_seconds() / 3600

            # 筛选出资金费率超过阈值的Bybit交易对，且必须是可交易的交易对
            data_list = [item for item in data 
                        if item.get('exchangeName') == 'Bybit' 
                        and abs(item.get('fundingRate', 0)) >= self.min_funding_rate * 100
                        and item.get('symbol') in available_symbols]

            for item in data_list:
                symbol = item.get('symbol')
                try:
                    # 验证交易对是否可以获取价格
                    ticker = self.client.get_tickers(
                        category="spot",
                        symbol=symbol
                    )
                    if ticker.get('retCode') != 0:
                        print(f"警告：无法获取交易对价格 - 交易对: {symbol}, 错误: {ticker.get('retMsg')}")
                        continue

                    funding_rate = float(item.get('fundingRate', 0))
                    # 计算预期收益率（考虑手续费和利息成本）
                    expected_profit = self.calculate_profit(funding_rate, holding_hours)
                    
                    # 如果预期收益率超过阈值，添加到套利机会列表
                    if abs(expected_profit) > self.min_funding_rate:
                        opportunities.append({
                            'symbol': symbol,
                            'funding_rate': funding_rate,
                            'expected_profit': expected_profit,
                            'direction': 'long' if funding_rate > 0 else 'short'
                        })

                except Exception as e:
                    print(f"警告：处理交易对数据失败 - 交易对: {symbol}, 错误: {str(e)}")
                    continue

        except Exception as e:
            print(f"错误：获取交易对信息失败 - {str(e)}")
            return []

        # 按预期收益率绝对值降序排序
        return sorted(opportunities, key=lambda x: abs(x['expected_profit']), reverse=True)

    def open_arbitrage_position(self, symbol: str, direction: str, amount: float):
        """开启套利仓位
        在合约和现货市场同时开立反向仓位，实现资金费率套利
        
        Args:
            symbol: 交易对名称（如'BTCUSDT'）
            direction: 交易方向，'long'表示合约做多现货做空，'short'表示合约做空现货做多
            amount: 开仓数量，以基础货币为单位（如BTC）
            
        注意：
            1. 合约和现货是反向开仓，以对冲价格风险
            2. 如果其中一个市场开仓失败，会自动平掉另一个市场的仓位
            3. 开仓成功后会记录持仓信息到self.positions中
        """
        # 检查是否已存在该交易对的仓位
        if symbol in self.positions:
            print(f"跳过开仓 - 交易对: {symbol} 已存在仓位，方向: {self.positions[symbol]['direction']}, 数量: {self.positions[symbol]['amount']}")
            return
            
        try:
            # 设置更大的接收窗口，处理时间同步问题
            self.client.recv_window = 60000
            
            # 获取交易对精度信息
            instrument_info = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            if instrument_info.get('retCode') != 0:
                raise Exception(f"获取交易对信息失败: {instrument_info.get('retMsg')}")
            
            # 获取数量精度和最小交易数量
            qty_step = float(instrument_info['result']['list'][0]['lotSizeFilter']['qtyStep'])
            min_qty = float(instrument_info['result']['list'][0]['lotSizeFilter'].get('minOrderQty', qty_step))
            
            # 获取当前余额
            current_balance = self.get_usdt_balance()
            if current_balance <= 0:
                raise Exception("账户余额不足")
                
            # 获取当前市场价格
            ticker_response = self.client.get_tickers(
                category="spot",
                symbol=symbol
            )
            if ticker_response.get('retCode') != 0:
                raise Exception(f"获取市场价格失败: {ticker_response.get('retMsg')}")
            
            current_price = float(ticker_response['result']['list'][0]['lastPrice'])
            
            # 根据精度处理下单数量，并确保不小于最小交易数量
            # 由于使用2倍杠杆，实际可用资金翻倍
            max_amount_by_balance = (current_balance * 2) / current_price  # 考虑价格计算最大可开仓数量
            adjusted_amount = max(min_qty, round(min(amount, max_amount_by_balance) / qty_step) * qty_step)
            
            # 设置合约端杠杆
            try:
                self.client.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buyLeverage="2",
                    sellLeverage="2"
                )
            except Exception as e:
                if 'leverage not modified' in str(e):
                    # 已经设置过2倍杠杆，再次设置就会报错
                    pass

            # 设置现货端杠杆
            self.client.set_leverage(
                category="spot",
                symbol=symbol,
                buyLeverage="2",
                sellLeverage="2"
            )
            
            # 合约端开仓
            side = 'Buy' if direction == 'long' else 'Sell'
            self.client.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=str(adjusted_amount),  # 转换为字符串，避免精度问题
                reduce_only=False
            )

            # 现货端开反向仓位（使用相同的币数量）
            spot_side = 'Sell' if direction == 'long' else 'Buy'
            # 计算现货交易的USDT价值
            spot_value = adjusted_amount * current_price
            self.client.place_order(
                category="spot",
                symbol=symbol,
                side=spot_side,
                order_type="Market",
                qty=str(round(spot_value, 6))  # 现货交易使用USDT价值
            )

            # 记录持仓信息
            self.positions[symbol] = {
                'direction': direction,
                'amount': adjusted_amount,
                'spot_amount': round(spot_value, 6),
                'open_time': datetime.utcnow()
            }

        except Exception as e:
            error_msg = f"开仓失败 - 币种: {symbol}, 方向: {direction}, 数量: {adjusted_amount}, 错误: {str(e)}"
            print(error_msg)
            # 如果其中一个订单失败，需要关闭另一个订单，避免单边持仓
            self.close_arbitrage_position(symbol)

    def get_usdt_balance(self) -> float:
        """获取USDT余额
        Returns:
            float: USDT可用余额，如果获取失败则返回0
        """
        try:
            # 根据是否为测试网络选择不同的账户类型
            response = self.client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            if response.get('retCode') == 0:
                # 检查返回数据结构
                result = response.get('result', {})
                if not result or 'list' not in result or not result['list']:
                    print("获取钱包余额失败 - 返回数据结构异常")
                    return 0
                USDT = result['list'][0]['coin'][0]
                avialable_balance = float(USDT['walletBalance']) - float(USDT['totalPositionIM']) - float(USDT['locked'])
                return float(avialable_balance)
            else:
                error_code = response.get('retCode')
                error_msg = response.get('retMsg', '未知错误')
                if error_code == 401:
                    print(f"API认证失败 - 请检查API密钥权限设置，确保已启用钱包和交易权限")
                else:
                    print(f"获取钱包余额失败 - 错误码: {error_code}, 错误信息: {error_msg}")
                return 0
        except Exception as e:
            print(f"获取钱包余额异常 - 错误: {str(e)}")
            if 'status code' in str(e).lower():
                print("API请求失败 - 请检查网络连接和API密钥配置")
            return 0

    def close_arbitrage_position(self, symbol: str):
        """关闭套利仓位
        同时平掉合约和现货的持仓，结束套利交易
        
        Args:
            symbol: 要平仓的交易对名称
            
        注意：
            1. 如果该交易对没有持仓，直接返回
            2. 合约和现货同时平仓，以清除所有风险敞口
            3. 平仓后会从self.positions中删除该交易对的记录
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        try:
            # 合约端平仓，与开仓方向相反
            side = 'Sell' if position['direction'] == 'long' else 'Buy'
            self.client.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=position['amount'],
                reduce_only=True  # 确保是平仓操作
            )

            # 现货端平仓，与开仓方向相反
            spot_side = 'Buy' if position['direction'] == 'long' else 'Sell'
            self.client.place_order(
                category="spot",
                symbol=symbol,
                side=spot_side,
                order_type="Market",
                marketUnit="quoteCoin",  # 使用USDT金额下单
                qty=position['spot_amount']
            )

            # 删除持仓记录
            del self.positions[symbol]

        except Exception as e:
            error_msg = f"平仓失败 - 币种: {symbol}, 方向: {position['direction']}, 现货数量: {position['spot_amount']}, 合约数量: {position['amount']}, 错误: {str(e)}"
            print(error_msg)

    def run(self):
        """运行策略
        主循环：
        1. 在资金费率结算前30分钟，寻找并执行新的套利机会
        2. 在资金费率结算前1分钟，关闭所有持仓
        3. 每分钟检查一次市场状态
        """
        while True:
            try:
                # 获取下一个资金费率结算时间
                next_funding_time = self.get_next_funding_time()
                now = datetime.utcnow()

                # 如果距离下次资金费率结算还有30分钟，寻找新的套利机会
                time_to_funding = (next_funding_time - now).total_seconds()
                if True:  # 在结算前30-29分钟之间开仓
                    # 寻找新的套利机会
                    opportunities = self.find_arbitrage_opportunities()
                    for opp in opportunities:
                        # 控制最大持仓数量，避免资金分散
                        if len(self.positions) >= 5:  # 最多同时持有5个币种的仓位
                            break

                        # 获取当前市场价格
                        symbol_price = float(self.client.get_tickers(
                            category="spot",
                            symbol=opp['symbol']
                        )['result']['list'][0]['lastPrice'])
                        
                        # 计算开仓数量，考虑最大持仓价值和账户余额限制
                        amount = min(
                            self.max_position_value / symbol_price,  # 最大持仓价值限制
                            float(self.get_usdt_balance()) / symbol_price / 2  # 确保资金足够开双向仓位
                        )

                        # 如果计算出的开仓数量大于0，执行开仓
                        if amount > 0:
                            self.open_arbitrage_position(
                                opp['symbol'],
                                opp['direction'],
                                amount
                            )

                # 在资金费率结算后1分钟关闭所有仓位
                elif time_to_funding < -60:  # 结算后1分钟
                    for symbol in list(self.positions.keys()):
                        self.close_arbitrage_position(symbol)

                time.sleep(60)  # 每分钟检查一次

            except Exception as e:
                error_msg = f"策略运行错误 - 时间: {datetime.utcnow()}, 错误: {str(e)}"
                if 'opportunities' in locals():
                    error_msg += f"\n当前套利机会: {opportunities}"
                print(error_msg)
                time.sleep(60)

if __name__ == "__main__":
    # 创建策略实例
    strategy = FundingRateArbitrage(
        api_key="0BWy5XSY1Vtbw2AEDj",
        api_secret="tY6wykBsfWy7I6opCgrmE1WnufafE4zZrnFL",
        test_net=True  # 测试网络
    )
    
    # 运行策略
    strategy.run()