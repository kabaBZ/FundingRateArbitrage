from decimal import Decimal

from typing import Union

# 预期结算时间
supported_arbitrage_timing_dict = {
    4: (4, 0, 0),
    8: (8, 0, 0),
    12: (12, 0, 0),
    16: (16, 0, 0),
    20: (20, 0, 0),
    24: (0, 0, 0),
}


def format_num_by_step(num, step) -> Decimal:
    """根据步长格式化数字,保留步长位数的小数"""
    return Decimal(int(Decimal(num) / Decimal(step))) * Decimal(step)
