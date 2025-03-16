from config import BYBIT_API_KEY, BYBIT_API_SECRET
from strategies.funding_rate_arbitrage import FundingRateArbitrage

if __name__ == "__main__":
    # 创建策略实例
    strategy = FundingRateArbitrage(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        demo=True,  # 模拟交易
    )

    # 运行策略
    strategy.run()