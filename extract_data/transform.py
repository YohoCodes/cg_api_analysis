# Converts raw CoinGecko payloads into tidy pandas DataFrames.

import datetime as dt
import pandas as pd


def reformat_data(chart_data):
    """
    Converts raw market chart data into a pandas DataFrame indexed by date.

    Parameters
    ----------
    chart_data : dict
        Raw chart data as returned by the CoinGecko API.

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
    # Extract prices
    prices = [pair[1] for pair in chart_data['prices']]

    # Assign dates (most recent date is today, going backwards)
    current_date = dt.date.today()
    timedelta = dt.timedelta(days=1)

    date_price = {}
    for i in range(len(prices)):
        index = -(i + 1)
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
