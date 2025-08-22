# Import modules
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
from pycoingecko import CoinGeckoAPI
from utils import Search

cg = CoinGeckoAPI()

class get_coin_market_chart_as_df:

    def __init__(self, id = 'bitcoin', vs_currency = 'usd', days = 360, interval = 'daily'):
        # Only allow daily interval since hourly is for enterprise users
        self.id = id
        self.vs_currency = vs_currency
        self.days = days
        self.interval = 'daily'  # force daily
        self.search = Search()

        # Retrieve raw chart data from CoinGecko API Wrapper
        cg = CoinGeckoAPI()
        self.raw_chart = cg.get_coin_market_chart_by_id(id = self.id, 
                                                        vs_currency = self.vs_currency, 
                                                        days = self.days, 
                                                        interval = self.interval)

    def reformat(self):
        # Extract prices
        prices = [pair[1] for pair in self.raw_chart['prices']]

        # Assign dates
        current_date = dt.datetime.today()

        # Determine timedelta (always daily)
        timedelta = dt.timedelta(days=1)

        # Dictionary creation loop
        date_price = {}
        for i in range(len(prices)):
            index = -(i+1)
            date_price[current_date] = prices[index]
            current_date -= timedelta

        # Convert to df
        df = pd.DataFrame(list(date_price.items()), columns=['date', 'price'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        return df

    def plot(self):
        df = self.reformat()
        plt.figure(figsize=(12, 6))
        plt.plot(df.index, df['price'], marker='o')
        plt.title(f"{self.id.capitalize()} Price Chart")
        plt.xlabel("Date")
        plt.ylabel("Price (USD)")
        plt.grid()
        plt.show()

if __name__ == "__main__":
    print(get_coin_market_chart_as_df().reformat())

