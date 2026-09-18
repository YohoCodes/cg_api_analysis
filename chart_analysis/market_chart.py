# Main class for chart analysis
# Data sourced from CoinGecko API (https://www.coingecko.com/en/api)

# Import modules
import extract_data

from .correlation import price_correlation, return_correlation
from .plotting import plot_prices


class analyze_coin_market_chart:
    """
    A class to retrieve, process, and analyze historical market chart data for one or more
    cryptocurrencies from the CoinGecko API. Provides methods for data conversion, correlation
    analysis, and plotting.

    Retrieval is delegated to the `extract_data` package; the analysis itself lives in
    `chart_analysis.correlation` and `chart_analysis.plotting`. Either layer can be used
    directly if you would rather not go through this class.

    Attributes
    ----------
    id : str or list of str
        The CoinGecko coin ID or list of IDs (default: 'bitcoin').
    vs_currency : str
        The target currency for market data (default: 'usd').
    days : int
        Number of days to retrieve data for (default: 364).
    interval : str
        Data interval. Only 'daily' is supported (enforced).
    precision : int or None
        Number of decimal places for price data (default: None, full precision).
    is_saved : bool
        Indicates whether data tables have been saved/cached.
    overwrite : bool
        Whether cached CSVs are ignored and re-downloaded.
    datasets_dir : str
        Directory holding the cached CSVs (default: 'datasets').
    cg : CoinGeckoAPI
        Instance of the CoinGeckoAPI client.
    saved_tables : dict
        Dictionary of DataFrames for each coin (only if id is a list).
    raw_chart : dict
        Raw chart data for a single coin (only if id is a string).
    top_coin_cache : extract_data.TopCoinsCache
        Day-scoped cache backing the top_coins() method.

    Methods
    -------
    reformat_data(chart_data=None):
        Converts raw market chart data into a pandas DataFrame indexed by date, with daily close and percent change.
    save_tables(coin_list=None):
        Saves reformatted market chart data tables for a list of coins to disk and memory.
    price_correlation():
        Computes the correlation of daily close prices between all pairs of coins (if multiple coins).
    return_correlation():
        Computes the correlation of daily returns (percent changes) between all pairs of coins (if multiple coins).
    top_coins(limit=5):
        Retrieves the top N coins by market cap from the CoinGecko API with caching.
    plot():
        Plots the price chart(s) for the coin(s) using the reformatted market chart data.
    """

    def __init__(self, id = 'bitcoin', vs_currency = 'usd', days = 364, limit = False, reset = False,
                 precision = None, overwrite = False, datasets_dir = extract_data.DATASETS_DIR,
                 client = None):
        """
        Initializes the analyze_coin_market_chart class.

        Parameters
        ----------
        id : str or list of str, optional
            The CoinGecko coin ID or list of IDs (default is 'bitcoin').
        vs_currency : str, optional
            The target currency (default is 'usd').
        days : int, optional
            Number of days of data to retrieve (default is 364).
            Due to free API limitations, 364 is the max possible value.
        limit : int or bool, optional
            If specified as an integer, automatically retrieves the top N coins by market cap
            from the CoinGecko API and uses them instead of the provided id parameter.
            If False (default), uses the provided id parameter as normal.
        reset : bool, optional
            If True, rebuilds the in-memory tables even when they are already cached.
        precision : int or None, optional
            Number of decimal places for price data (default: None, full precision).
            Setting this rounds sub-cent coins, so leave it alone unless you need it.
        overwrite : bool, optional
            If True, ignore any cached CSV in datasets_dir and re-download (default: False).
        datasets_dir : str, optional
            Directory holding the cached CSVs (default: 'datasets').
        client : CoinGeckoAPI, optional
            Existing client to reuse. A new one is created when omitted.
        """
        # Only allow daily interval since hourly is for enterprise users
        self.id = id
        self.vs_currency = vs_currency
        self.days = days
        self.interval = extract_data.INTERVAL
        self.precision = precision
        self.is_saved = False
        self.cg = client or extract_data.get_client()
        self.reset = reset
        self.overwrite = overwrite
        self.datasets_dir = datasets_dir
        self.top_coin_cache = extract_data.TopCoinsCache(vs_currency=vs_currency, client=self.cg)

        # If limit is set, save the top coins using API call in top_coins() method.
        if limit:
            self.id = self.top_coins(limit = limit)

        # If the id is a list, save the tables
        if isinstance(self.id, list):
            # Remove any None or invalid ids from the list
            self.id = extract_data.clean_coin_ids(self.id)
            if not self.id:
                raise ValueError("No valid coin IDs provided.")
            self.save_tables(self.id)

        # If the id is a string, retrieve the raw chart data
        else:
            try:
                self.raw_chart = extract_data.fetch_market_chart(
                    self.id,
                    vs_currency=self.vs_currency,
                    # Add 1 day since pct_change is null for first day
                    days=self.days + 1,
                    precision=self.precision,
                    client=self.cg
                )
                self.is_saved = True
            except Exception as e:
                raise ValueError(f"Error retrieving data for coin id '{self.id}': {e}")

    def reformat_data(self, chart_data=None):
        """
        Converts the raw market chart data into a pandas DataFrame indexed by date.

        Parameters
        ----------
        chart_data : dict, optional
            Raw chart data as returned by CoinGecko API. If None, uses self.raw_chart.

        Returns
        -------
        pd.DataFrame
            DataFrame indexed by date with columns:
            - 'daily_close': closing price for the day
            - 'percent_change': daily percent change in price (%)
        """
        if chart_data is None:
            chart_data = self.raw_chart

        return extract_data.reformat_data(chart_data)

    def save_tables(self, coin_list=None):
        """
        Saves reformatted market chart data tables for a list of coins.

        For each coin in the provided coin_list, a cached CSV is loaded when present;
        otherwise the CoinGecko API is called and the reformatted table written to
        `datasets/`. Tables are stored in self.saved_tables, keyed by coin ID, and coins
        that could not be retrieved are dropped from self.id.

        Parameters
        ----------
        coin_list : list of str, optional
            A list of coin IDs for which to save the reformatted data tables. If None, uses self.id.

        Returns
        -------
        None
            Updates self.saved_tables, self.id and self.is_saved attributes.
        """
        if coin_list is None:
            coin_list = self.id
        if self.reset:
            self.is_saved = False

        # Check if the tables are already cached
        elif self.is_saved:
            print("Tables already cached. Skipping save.")
            return

        self.saved_tables, failed_coins = extract_data.get_market_tables(
            coin_list,
            vs_currency=self.vs_currency,
            days=self.days,
            overwrite=self.overwrite,
            datasets_dir=self.datasets_dir,
            client=self.cg
        )

        # Remove failed coins from coin_list and update self.id
        self.id = [coin for coin in coin_list if coin not in failed_coins]

        # Save global is_saved variable
        self.is_saved = True

        print(f"\n{len(self.id)} tables saved!\n")

    def price_correlation(self):
        """
        Computes the correlation of daily close prices between all pairs of coins.

        Pairs whose correlation is undefined - a coin that never varies, or one
        holding non-finite values - are left out of the ranking, and an explanation
        naming the coins and the remedy is printed.

        Returns
        -------
        pd.DataFrame or None
            DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair
            with a defined correlation, sorted by correlation (descending). Returns None
            if fewer than two coins are available, if they share fewer than two dates, or
            if no pair has a defined correlation; the reason is printed in each case.
        """
        # If only one coin, correlation is not defined
        if isinstance(self.id, str):
            print("Correlation analysis requires at least two coins.")
            return None

        ranking = price_correlation(self.saved_tables, coin_ids=self.id)

        if ranking is not None:
            print('Correlation of price between all pairs of coins:\n')

        return ranking

    def return_correlation(self):
        """
        Computes the correlation of percent changes (daily returns) between all pairs of coins.

        Pairs whose correlation is undefined - a coin that never varies, or one
        holding non-finite values - are left out of the ranking, and an explanation
        naming the coins and the remedy is printed.

        Returns
        -------
        pd.DataFrame or None
            DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair
            with a defined correlation, sorted by correlation (descending). Returns None
            if fewer than two coins are available, if they share fewer than two dates, or
            if no pair has a defined correlation; the reason is printed in each case.
        """
        # If only one coin, correlation is not defined
        if isinstance(self.id, str):
            print("Correlation analysis requires at least two coins.")
            return None

        ranking = return_correlation(self.saved_tables, coin_ids=self.id)

        if ranking is not None:
            print('Correlation of daily returns between all pairs of coins:\n')

        return ranking

    def top_coins(self, limit = 5):
        """
        Retrieves the top coins by market cap from the CoinGecko API with intelligent caching.

        Caching is handled by extract_data.TopCoinsCache: if the same limit was requested
        today, the cached list is returned instead of making a new API call.

        Parameters
        ----------
        limit : int, optional
            The number of top coins to retrieve (default: 5).

        Returns
        -------
        list of str
            List of coin IDs sorted by market cap (descending).
            Returns empty list if API call fails.
        """
        return self.top_coin_cache.get(limit=limit)

    def plot(self):
        """
        Plots the price chart for the coin or coins using the reformatted market chart data.

        If self.id is a list, plots each coin's price chart in a separate subplot.
        If self.id is a string, plots a single price chart.

        Returns
        -------
        None
            Displays the plot(s) using matplotlib.
        """
        # If id is a list, plot each coin in a separate subplot
        if isinstance(self.id, list):
            plot_prices(self.saved_tables, vs_currency=self.vs_currency, coin_ids=self.id)
        else:
            # Single coin plot
            plot_prices({self.id: self.reformat_data()}, vs_currency=self.vs_currency)
