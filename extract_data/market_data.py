# Cache-aware retrieval of market chart tables.

import datetime as dt

from .client import DEFAULT_DAYS, DEFAULT_VS_CURRENCY, fetch_market_chart, fetch_top_coins, get_client
from .storage import DATASETS_DIR, dataset_path, has_table, load_table, save_table
from .transform import reformat_data


def clean_coin_ids(coin_ids):
    """
    Drops None, non-string and blank entries from a list of coin IDs.

    Parameters
    ----------
    coin_ids : list
        Candidate coin IDs.

    Returns
    -------
    list of str
        Only the usable coin IDs, in their original order.
    """
    return [coin for coin in coin_ids
            if coin is not None and isinstance(coin, str) and coin.strip() != ""]


def get_market_chart_table(coin_id, vs_currency=DEFAULT_VS_CURRENCY, days=DEFAULT_DAYS,
                           precision=None, client=None):
    """
    Retrieves and reformats one coin's market chart in a single step.

    Parameters
    ----------
    coin_id : str
        The CoinGecko coin ID.
    vs_currency : str, optional
        The target currency (default: 'usd').
    days : int, optional
        Number of days of data (default: 364). One extra day is requested
        internally because percent change is null for the first day.
    precision : int or None, optional
        Number of decimal places for price data (default: None, full precision).
    client : CoinGeckoAPI, optional
        Existing client to reuse.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date with 'daily_close' and 'percent_change' columns.
    """
    raw_chart = fetch_market_chart(
        coin_id,
        vs_currency=vs_currency,
        # Add 1 day since pct_change is null for the first day
        days=days + 1,
        precision=precision,
        client=client
    )
    return reformat_data(raw_chart)


def get_market_tables(coin_ids, vs_currency=DEFAULT_VS_CURRENCY, days=DEFAULT_DAYS,
                      overwrite=False, datasets_dir=DATASETS_DIR, client=None):
    """
    Retrieves reformatted market chart tables for a list of coins, using the disk cache.

    For each coin, a cached CSV is loaded when present; otherwise the CoinGecko API is
    called, the result reformatted, and the table written to the cache. Coins that fail
    or return too little data are reported rather than raising.

    Parameters
    ----------
    coin_ids : list of str
        Coin IDs to retrieve.
    vs_currency : str, optional
        The target currency (default: 'usd').
    days : int, optional
        Number of days of data (default: 364).
    overwrite : bool, optional
        If True, ignore any cached CSV and re-download (default: False).
    datasets_dir : str, optional
        Directory holding the cached CSVs (default: 'datasets').
    client : CoinGeckoAPI, optional
        Existing client to reuse. A new one is created when omitted.

    Returns
    -------
    tuple of (dict, list)
        - dict mapping coin ID to its DataFrame, for every coin retrieved
        - list of coin IDs that could not be retrieved
    """
    client = client or get_client()

    tables = {}
    failed_coins = []

    for coin in coin_ids:
        # Defensive: skip None or empty coin ids
        if coin is None or not isinstance(coin, str) or coin.strip() == "":
            print(f"Skipping invalid coin id: {coin}")
            failed_coins.append(coin)
            continue

        file_name = dataset_path(coin, vs_currency, days, datasets_dir=datasets_dir)

        if has_table(file_name) and not overwrite:
            # Load from CSV if file exists
            tables[coin] = load_table(file_name)
            print(f"Loaded chart for {coin} from file.")
            continue

        try:
            # Only call API if file does not exist
            raw_chart = fetch_market_chart(
                coin,
                vs_currency=vs_currency,
                # Add 1 day since pct_change is null for the first day
                days=days + 1,
                client=client
            )

            # Reformat data into a dataframe and save it
            if len(raw_chart['prices']) >= .5 * days:
                tables[coin] = reformat_data(raw_chart)
                save_table(tables[coin], file_name)
                print(f"Saved chart for {coin}...")

            # Handle insufficient data
            else:
                print(f"Insufficient data found for {coin}")
                failed_coins.append(coin)

        # Handle API call errors
        except Exception as e:
            print(f"Error retrieving data for {coin}: {e}")
            failed_coins.append(coin)

    return tables, failed_coins


class TopCoinsCache:
    """
    Retrieves the top coins by market cap, caching the result for the day.

    A fresh API call is made only when the cached list was built on an earlier date
    or for a different limit.

    Attributes
    ----------
    vs_currency : str
        The currency used to rank market caps.
    client : CoinGeckoAPI
        Client used for the lookups.
    coins : list of str or None
        The cached list of coin IDs.
    date_of_save : datetime.date or None
        Date the cached list was retrieved.
    last_limit : int or None
        Limit used for the cached list.
    """

    def __init__(self, vs_currency=DEFAULT_VS_CURRENCY, client=None):
        """
        Initializes an empty cache.

        Parameters
        ----------
        vs_currency : str, optional
            The currency used to rank market caps (default: 'usd').
        client : CoinGeckoAPI, optional
            Existing client to reuse. A new one is created when omitted.
        """
        self.vs_currency = vs_currency
        self.client = client or get_client()
        self.coins = None
        self.date_of_save = None
        self.last_limit = None

    def get(self, limit=5):
        """
        Returns the top `limit` coins by market cap.

        Parameters
        ----------
        limit : int, optional
            The number of top coins to retrieve (default: 5).

        Returns
        -------
        list of str
            List of coin IDs sorted by market cap (descending).
            Returns an empty list if the API call fails.
        """
        # Reuse the cached list when it was built today for the same limit
        if (self.coins is not None
                and self.date_of_save == dt.date.today()
                and self.last_limit == limit):
            return self.coins

        coins = fetch_top_coins(limit=limit, vs_currency=self.vs_currency, client=self.client)
        if coins:
            self.coins = coins
            self.date_of_save = dt.date.today()
            self.last_limit = limit
        return coins
