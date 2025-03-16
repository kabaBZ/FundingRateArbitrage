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
    # import json
    # from ArbitrageData.arbitrage_list import get_bybit_interestArbitrage_data
    # arbitrage_list = get_bybit_interestArbitrage_data()
    # with open("arbitrage_list.json", "w") as f:
    #     json.dump(arbitrage_list, f)