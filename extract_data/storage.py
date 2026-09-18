# On-disk cache for reformatted market chart tables.

import os
import pandas as pd

# Directory the cached CSVs live in, relative to the working directory.
DATASETS_DIR = 'datasets'


def dataset_path(coin_id, vs_currency, days, datasets_dir=DATASETS_DIR):
    """
    Builds the cache file path for one coin's market chart table.

    Parameters
    ----------
    coin_id : str
        The CoinGecko coin ID.
    vs_currency : str
        The target currency the data was retrieved in.
    days : int
        Number of days the table covers.
    datasets_dir : str, optional
        Directory holding the cached CSVs (default: 'datasets').

    Returns
    -------
    str
        Path to the CSV file for this coin.
    """
    return os.path.join(datasets_dir, f'{coin_id}_{vs_currency}_{days}days.csv')


def has_table(path):
    """
    Reports whether a cached table exists at the given path.

    Parameters
    ----------
    path : str
        Path to a cached CSV file.

    Returns
    -------
    bool
        True if the file exists.
    """
    return os.path.exists(path)


def load_table(path):
    """
    Loads a cached market chart table from disk.

    Parameters
    ----------
    path : str
        Path to a cached CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date, as written by save_table.
    """
    return pd.read_csv(path, index_col='date', parse_dates=True)


def save_table(df, path):
    """
    Writes a market chart table to disk, creating the directory if needed.

    Parameters
    ----------
    df : pd.DataFrame
        Reformatted market chart data, indexed by date.
    path : str
        Destination CSV path.

    Returns
    -------
    None
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    df.to_csv(path)
