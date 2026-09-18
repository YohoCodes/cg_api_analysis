"""
Shared fixtures for the analysis tests.

Analysis functions take {coin_id: DataFrame} mappings, so the tests build those
frames directly instead of going anywhere near the CoinGecko API.
"""

import contextlib
import io

import pandas as pd


def make_table(closes, start='2024-01-01'):
    """
    Builds a market chart table shaped like extract_data.reformat_data's output.

    Parameters
    ----------
    closes : list of float
        Daily close prices, oldest first.
    start : str, optional
        Date of the first close (default: '2024-01-01').

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date with 'daily_close' and 'percent_change' columns,
        with the undefined first percent change dropped.
    """
    # Built without a freq so the index matches what reformat_data produces.
    index = pd.DatetimeIndex(
        pd.date_range(start, periods=len(closes), freq='D').tolist(), name='date'
    )
    df = pd.DataFrame({'daily_close': list(closes)}, index=index)
    df['percent_change'] = df['daily_close'].pct_change() * 100
    return df.dropna(subset=['percent_change'])


def make_tables(spec, start='2024-01-01'):
    """
    Builds several tables at once.

    Parameters
    ----------
    spec : dict
        Maps coin ID to its list of close prices.
    start : str, optional
        Date of the first close, shared by every coin (default: '2024-01-01').

    Returns
    -------
    dict
        Maps coin ID to its DataFrame.
    """
    return {coin: make_table(closes, start=start) for coin, closes in spec.items()}


def capture(fn, *args, **kwargs):
    """
    Runs a function and captures anything it prints.

    Parameters
    ----------
    fn : callable
        The function to run.
    *args, **kwargs
        Passed through to fn.

    Returns
    -------
    tuple of (object, str)
        The function's return value and everything it wrote to stdout.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = fn(*args, **kwargs)
    return result, buffer.getvalue()
