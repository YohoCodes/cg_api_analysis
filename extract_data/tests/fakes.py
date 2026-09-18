"""
Test doubles standing in for the CoinGecko API.

Every test in this package injects one of these instead of a real client, so the
suite never touches the network and never depends on live market data.
"""


def price_payload(prices, start_ms=1700000000000, step_ms=86400000):
    """
    Builds a raw market chart payload of the shape CoinGecko returns.

    Parameters
    ----------
    prices : list of float
        Close prices, oldest first.
    start_ms : int, optional
        Timestamp of the first point, in milliseconds.
    step_ms : int, optional
        Spacing between points, in milliseconds (default: one day).

    Returns
    -------
    dict
        A payload with a 'prices' list of [timestamp, price] pairs.
    """
    return {'prices': [[start_ms + i * step_ms, price] for i, price in enumerate(prices)]}


class FakeCoinGeckoClient:
    """
    Records calls and replays canned responses.

    Attributes
    ----------
    charts : dict
        Maps coin ID to the payload to return, or to an Exception to raise.
    markets : list or Exception
        Response for get_coins_markets, or an Exception to raise.
    chart_calls : list of dict
        Keyword arguments of every get_coin_market_chart_by_id call, in order.
    market_calls : list of dict
        Keyword arguments of every get_coins_markets call, in order.
    """

    def __init__(self, charts=None, markets=None):
        self.charts = charts if charts is not None else {}
        self.markets = markets if markets is not None else []
        self.chart_calls = []
        self.market_calls = []

    def get_coin_market_chart_by_id(self, **kwargs):
        """Replays the canned chart for kwargs['id'], raising if one was configured."""
        self.chart_calls.append(kwargs)

        coin_id = kwargs.get('id')
        if coin_id not in self.charts:
            raise ValueError(f"FakeCoinGeckoClient has no chart configured for '{coin_id}'")

        response = self.charts[coin_id]
        if isinstance(response, Exception):
            raise response
        return response

    def get_coins_markets(self, **kwargs):
        """Replays the canned markets response, raising if one was configured."""
        self.market_calls.append(kwargs)

        if isinstance(self.markets, Exception):
            raise self.markets
        return self.markets
