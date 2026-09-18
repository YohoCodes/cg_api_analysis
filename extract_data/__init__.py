"""
Data extraction for the CoinGecko API.

Everything that talks to CoinGecko or to the on-disk CSV cache lives here.
The analysis side (chart_analysis) consumes the DataFrames these functions return.
"""

from .client import (
    API_KEY_ENV,
    DEFAULT_DAYS,
    DEFAULT_PRECISION,
    DEFAULT_VS_CURRENCY,
    DEMO_API_KEY_ENV,
    INTERVAL,
    describe_credentials,
    fetch_market_chart,
    fetch_top_coins,
    get_client,
)
from .market_data import (
    TopCoinsCache,
    clean_coin_ids,
    get_market_chart_table,
    get_market_tables,
)
from .storage import DATASETS_DIR, dataset_path, has_table, load_table, save_table
from .transform import reformat_data

__all__ = [
    'API_KEY_ENV',
    'DATASETS_DIR',
    'DEFAULT_DAYS',
    'DEFAULT_PRECISION',
    'DEFAULT_VS_CURRENCY',
    'DEMO_API_KEY_ENV',
    'INTERVAL',
    'TopCoinsCache',
    'clean_coin_ids',
    'dataset_path',
    'describe_credentials',
    'fetch_market_chart',
    'fetch_top_coins',
    'get_client',
    'get_market_chart_table',
    'get_market_tables',
    'has_table',
    'load_table',
    'reformat_data',
    'save_table',
]
