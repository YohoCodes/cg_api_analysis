# Main class for chart analysis
# Data sourced from CoinGecko API (https://www.coingecko.com/en/api)

# Import modules
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
from pycoingecko import CoinGeckoAPI
from itertools import combinations
import os

class analyze_coin_market_chart:
    """
    A class to retrieve, process, and analyze historical market chart data for one or more cryptocurrencies
    from the CoinGecko API. Provides methods for data conversion, correlation analysis, and plotting.

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
    precision : int
        Number of decimal places for price data (default: 2).
    is_saved : bool
        Indicates whether data tables have been saved/cached.
    cg : CoinGeckoAPI
        Instance of the CoinGeckoAPI client.
    saved_tables : dict
        Dictionary of DataFrames for each coin (only if id is a list).
    raw_chart : dict
        Raw chart data for a single coin (only if id is a string).
    top_coins : list
        List of top coins by market cap (cached for reuse).
    date_of_save : datetime.date
        Date when top coins were last retrieved (for caching).
    last_top_coin_limit : int
        Last limit used for top coins retrieval (for caching).

    Methods
    -------
    reformat_data(chart_data=None):
        Converts raw market chart data into a pandas DataFrame indexed by date, with daily close and percent change.
    save_tables(coin_list, reset=False):
        Saves reformatted market chart data tables for a list of coins to disk and memory.
    price_correlation():
        Computes the correlation of daily close prices between all pairs of coins (if multiple coins).
    return_correlation():
        Computes the correlation of daily returns (percent changes) between all pairs of coins (if multiple coins).
    correlation_analysis():
        Computes the correlation of percent changes between all pairs of coins (if multiple coins) - legacy method.
    top_coins(limit=5):
        Retrieves the top N coins by market cap from the CoinGecko API with caching.
    plot():
        Plots the price chart(s) for the coin(s) using the reformatted market chart data.
    """

    def __init__(self, id = 'bitcoin', vs_currency = 'usd', days = 364, limit = False, reset = False):
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
        """
        # Only allow daily interval since hourly is for enterprise users
        self.id = id
        self.vs_currency = vs_currency
        self.days = days
        self.interval = 'daily'
        self.precision = 2
        self.is_saved = False
        self.cg = CoinGeckoAPI()
        self.reset = reset

        # If limit is set, save the top coins using API call in top_coins() method.
        if limit:
            self.id = self.top_coins(limit = limit)

        # If the id is a list, save the tables
        if isinstance(self.id, list):
            # Remove any None or invalid ids from the list
            self.id = [coin for coin in self.id if coin is not None and isinstance(coin, str) and coin.strip() != ""]
            if not self.id:
                raise ValueError("No valid coin IDs provided.")
            self.save_tables(self.id)

        # If the id is a string, retrieve the raw chart data
        else:
            # Defensive: check for None or empty string
            if self.id is None or not isinstance(self.id, str) or self.id.strip() == "":
                raise ValueError("A valid coin id must be provided (got None or empty string).")
            try:
                self.raw_chart = self.cg.get_coin_market_chart_by_id(
                    id=self.id,
                    vs_currency=self.vs_currency, 
                    # Add 1 day since pct_change is null for first day
                    days=self.days+1,
                    interval=self.interval,
                    precision=self.precision
                )
                # Check if the API returned an error or empty data
                if not self.raw_chart or 'prices' not in self.raw_chart or len(self.raw_chart['prices']) == 0:
                    raise ValueError(f"No data found for coin id '{self.id}'.")
                self.is_saved = True
            except Exception as e:
                raise ValueError(f"Error retrieving data for coin id '{self.id}': {e}")

    def reformat_data(self, chart_data=None):
        """
        Converts the raw market chart data into a pandas DataFrame indexed by date.

        This method processes raw CoinGecko API data and converts it into a structured pandas DataFrame
        with daily close prices and percent changes. It handles date indexing and calculates daily returns.

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

        Notes
        -----
        - Dates are assigned in reverse chronological order (most recent first)
        - Percent change is calculated as ((current_price - previous_price) / previous_price) * 100
        - Rows with NaN percent changes (first day) are automatically dropped
        - DataFrame is sorted by date (ascending)
        """
        if chart_data is not None:
            # Extract prices
            prices = [pair[1] for pair in chart_data['prices']]
        else:
            prices = [pair[1] for pair in self.raw_chart['prices']]

        # Assign dates (most recent date is today, going backwards)
        current_date = dt.date.today()
        timedelta = dt.timedelta(days=1)

        date_price = {}
        for i in range(len(prices)):
            index = -(i+1)
            date_price[current_date] = prices[index]
            current_date -= timedelta

        # Convert to DataFrame
        df = pd.DataFrame(list(date_price.items()), columns=['date', 'daily_close'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        # Add percent change column
        df['percent_change'] = df['daily_close'].pct_change() * 100
        df.dropna(inplace=True, subset=['percent_change'])

        return df

    def save_tables(self, coin_list):
        """
        Saves reformatted market chart data tables for a list of coins.

        For each coin in the provided coin_list, this method reformats the raw market chart data
        into a pandas DataFrame and stores it in the self.saved_tables dictionary, with the coin's ID as the key.
        If a table already exists on disk, it is loaded from file instead of calling the API.
        After saving the tables, sets the is_saved attribute to True.

        Parameters
        ----------
        coin_list : list of str
            A list of coin IDs for which to save the reformatted data tables.
        reset : bool, optional
            If True, forces regeneration of tables even if already cached (default: False).

        Returns
        -------
        None
            Updates self.saved_tables and self.is_saved attributes.
        """
        if self.reset:
            self.is_saved = False

        # Check if the tables are already cached
        elif self.is_saved:
            print("Tables already cached. Skipping save.")
            return

        # Create a dictionary to store the tables
        self.saved_tables = {}
        failed_coins = []

        # Create a table for each coin
        for coin in coin_list:
            # Defensive: skip None or empty coin ids
            if coin is None or not isinstance(coin, str) or coin.strip() == "":
                print(f"Skipping invalid coin id: {coin}")
                failed_coins.append(coin)
                continue

            # Create a file name for the table
            file_name = f'datasets/{coin}_{self.vs_currency}_{self.days}days.csv'

            if os.path.exists(file_name):
                # Load from CSV if file exists
                self.saved_tables[coin] = pd.read_csv(file_name, index_col='date', parse_dates=True)
                print(f"Loaded chart for {coin} from file.")
            else:
                try:
                    # Only call API if file does not exist
                    raw_chart = self.cg.get_coin_market_chart_by_id(
                        id=coin,
                        vs_currency=self.vs_currency,
                        days=self.days + 1,  # Add 1 day since pct_change is null for first day
                        interval=self.interval
                    )

                    # Reformat data into a dataframe and save it
                    if raw_chart and 'prices' in raw_chart and len(raw_chart['prices']) >= .5 * self.days:
                        self.saved_tables[coin] = self.reformat_data(raw_chart)
                        self.saved_tables[coin].to_csv(file_name)
                        print(f"Saved chart for {coin}...")

                    # Handle empty dataframe    
                    else:
                        print(f"Insufficient data found for {coin}")
                        failed_coins.append(coin)
                        continue

                # Handle API call errors
                except Exception as e:
                    print(f"Error retrieving data for {coin}: {e}")
                    failed_coins.append(coin)
                    continue

        # Remove failed coins from coin_list and update self.id
        self.id = [coin for coin in coin_list if coin not in failed_coins]

        # Save global is_saved variable
        self.is_saved = True

        print(f"\n{len(self.id)} tables saved!\n")

    def price_correlation(self):
        """
        Computes the correlation of daily close prices between all pairs of coins.

        If self.id is a list, uses the saved_tables for each coin.
        If self.id is a string, returns None (not enough data for correlation).

        Returns
        -------
        pd.DataFrame or None
            DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair,
            sorted by correlation (descending). Returns None if only one coin is provided.
        """
        # If only one coin, correlation is not defined
        if isinstance(self.id, str):
            print("Correlation analysis requires at least two coins.")
            return None

        # Use saved_tables to build price DataFrame
        first = True
        for id, table in self.saved_tables.items():
            # First iteration creates initial dataframe
            if first:
                coin_comparison = table[['daily_close']].rename(columns={'daily_close': id})
                first = False
            else:
                # Subsequent iterations join the new table to the existing dataframe on index
                slice = table[['daily_close']].rename(columns={'daily_close': id})
                coin_comparison = coin_comparison.join(slice)

        # Drop rows with any NaN to ensure proper alignment
        coin_comparison = coin_comparison.dropna()

        # Calculate the correlation matrix
        corr_matrix = coin_comparison.corr()

        # Save all unique combinations of coin ids
        pairs = combinations(self.id, 2)

        # Prepare data for DataFrame
        data = []
        for coin1, coin2 in pairs:
            corr = corr_matrix.at[coin1, coin2]
            data.append({'coin1': coin1, 'coin2': coin2, 'correlation': corr})

        # Save the correlation matrix to a variable
        correlation_ranking = pd.DataFrame(data, columns=['coin1', 'coin2', 'correlation']).sort_values(by=['correlation'], ascending=False)
        correlation_ranking = correlation_ranking.dropna()
        correlation_ranking = correlation_ranking.reset_index(drop=True)

        print('Correlation of price between all pairs of coins:\n')

        return correlation_ranking

    def return_correlation(self):
        """
        Computes the correlation of percent changes (daily returns) between all pairs of coins.

        If self.id is a list, uses the saved_tables for each coin.
        If self.id is a string, returns None (not enough data for correlation).

        Returns
        -------
        pd.DataFrame or None
            DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair,
            sorted by correlation (descending). Returns None if only one coin is provided.
        """
        # If only one coin, correlation is not defined
        if isinstance(self.id, str):
            print("Correlation analysis requires at least two coins.")
            return None

        # Use saved_tables to build percent change DataFrame
        first = True
        for id, table in self.saved_tables.items():
            # First iteration creates initial dataframe
            if first:
                coin_comparison = table[['percent_change']].rename(columns={'percent_change': id})
                first = False
            else:
                # Subsequent iterations join the new table to the existing dataframe on index
                slice = table[['percent_change']].rename(columns={'percent_change': id})
                coin_comparison = coin_comparison.join(slice)

        # Drop rows with any NaN to ensure proper alignment
        coin_comparison = coin_comparison.dropna()

        # Calculate the correlation matrix
        corr_matrix = coin_comparison.corr()

        # Save all unique combinations of coin ids
        pairs = combinations(self.id, 2)

        # Prepare data for DataFrame
        data = []
        for coin1, coin2 in pairs:
            corr = corr_matrix.at[coin1, coin2]
            data.append({'coin1': coin1, 'coin2': coin2, 'correlation': corr})

        # Save the correlation matrix to a variable
        correlation_ranking = pd.DataFrame(data, columns=['coin1', 'coin2', 'correlation']).sort_values(by=['correlation'], ascending=False)
        correlation_ranking = correlation_ranking.dropna()
        correlation_ranking = correlation_ranking.reset_index(drop=True)

        print('Correlation of daily returns between all pairs of coins:\n')

        return correlation_ranking

    def top_coins(self, limit = 5):
        """
        Retrieves the top coins by market cap from the CoinGecko API with intelligent caching.

        This method fetches the top N cryptocurrencies by market capitalization from the CoinGecko API.
        It implements caching to avoid unnecessary API calls - if the same limit was requested today,
        it returns the cached result instead of making a new API call.

        Parameters
        ----------
        limit : int, optional
            The number of top coins to retrieve (default: 5).

        Returns
        -------
        list of str
            List of coin IDs sorted by market cap (descending).
            Returns empty list if API call fails.

        Notes
        -----
        - Caching is based on the current date and the limit parameter
        - Cache is automatically invalidated on a new day
        - API failures are handled gracefully with error messages
        """
        # Check if the saved date matches today's date and the last limit used matches the current limit
        try:
            if (self.date_of_save == dt.date.today()) and (self.last_top_coin_limit == limit):
                # If so, return the cached list of top coins
                return self.top_coins
        except:
            # if there is no date of save, then top coins are not already cached
            # so we can just return the top coins with the else statement
            pass

        # Always fetch fresh list if not cached
        try:
            top_coins_by_market_cap = CoinGeckoAPI().get_coins_markets(
                vs_currency='usd',
                order='market_cap_desc',
                per_page=limit,
                page=1,
                sparkline=False
            )
            # Extract the 'id' of each coin and save to self.top_coins
            self.top_coins = [record['id'] for record in top_coins_by_market_cap if record.get('id')]
            # Update the date of save and the last limit used
            self.date_of_save = dt.date.today()
            self.last_top_coin_limit = limit
            # Return the updated list of top coins
            return self.top_coins
        except Exception as e:
            print(f"Error retrieving top coins: {e}")
            return []

    def plot(self):
        """
        Plots the price chart for the coin or coins using the reformatted market chart data.

        Creates matplotlib visualizations of cryptocurrency price data. For multiple coins,
        creates separate subplots for each coin. For a single coin, creates a single plot.

        If self.id is a list, plots each coin's price chart in a separate subplot.
        If self.id is a string, plots a single price chart.

        Returns
        -------
        None
            Displays the plot(s) using matplotlib.

        Notes
        -----
        - Uses daily close prices for plotting
        - Automatically handles both single and multiple coin scenarios
        - Subplot layout adjusts based on number of coins
        - Includes grid lines and proper axis labels
        """
        # If id is a list, plot each coin in a separate subplot
        if isinstance(self.id, list):
            num_coins = len(self.id)
            fig, axes = plt.subplots(num_coins, 1, figsize=(12, 5 * num_coins), sharex=False)
            if num_coins == 1:
                axes = [axes]  # Make axes iterable if only one coin

            for ax, coin in zip(axes, self.id):
                # Plot daily close prices
                df = self.saved_tables[coin]
                ax.plot(df.index, df['daily_close'], marker='o')
                ax.set_title(f"{coin.capitalize()} Price Chart")
                ax.set_xlabel("Date")
                ax.set_ylabel(f"Price ({self.vs_currency.upper()})")
                ax.grid()

            plt.tight_layout()
            plt.show()
        else:
            # Single coin plot
            df = self.reformat_data()
            plt.figure(figsize=(12, 6))
            plt.plot(df.index, df['daily_close'], marker='o')
            plt.title(f"{self.id.capitalize()} Price Chart")
            plt.xlabel("Date")
            plt.ylabel(f"Price ({self.vs_currency.upper()})")
            plt.grid()
            plt.show()
            plt.show()