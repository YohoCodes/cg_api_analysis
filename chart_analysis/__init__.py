"""
Analysis and plotting for CoinGecko market chart data.

These functions operate on the DataFrames produced by the `extract_data` package:
dicts of {coin_id: DataFrame} indexed by date, with 'daily_close' and 'percent_change'
columns. `analyze_coin_market_chart` wires the two packages together for convenience.
"""

from .correlation import price_correlation, return_correlation
from .market_chart import analyze_coin_market_chart
from .plotting import plot_price, plot_prices

__all__ = [
    'analyze_coin_market_chart',
    'plot_price',
    'plot_prices',
    'price_correlation',
    'return_correlation',
]
