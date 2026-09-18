# Thin wrappers around the CoinGecko API.
# Data sourced from CoinGecko API (https://www.coingecko.com/en/api)

import os

from pycoingecko import CoinGeckoAPI

# Only 'daily' is supported: hourly data is an enterprise-only feature.
INTERVAL = 'daily'

DEFAULT_VS_CURRENCY = 'usd'
DEFAULT_DAYS = 364
DEFAULT_PRECISION = 2

# Credentials are read from the environment so that no key is ever written to a
# file in the working tree. Demo and Pro keys are not interchangeable: they use
# different base URLs and different request headers.
API_KEY_ENV = 'COINGECKO_API_KEY'            # paid Pro plans
DEMO_API_KEY_ENV = 'COINGECKO_DEMO_API_KEY'  # free Demo accounts


def _from_env(name):
    """
    Reads a credential from the environment.

    Parameters
    ----------
    name : str
        Environment variable to read.

    Returns
    -------
    str
        The value with surrounding whitespace removed, or '' when unset. A
        variable set to blank counts as unset, so an empty export does not
        silently switch the client to a paid endpoint.
    """
    return os.environ.get(name, '').strip()


def get_client(api_key=None, demo_api_key=None):
    """
    Creates a CoinGecko API client, authenticated from the environment.

    Credentials come from the COINGECKO_API_KEY (Pro) and COINGECKO_DEMO_API_KEY
    (Demo) environment variables unless passed explicitly. With neither set, the
    client uses the unauthenticated public endpoint, which has the tightest rate
    limits. A Pro key takes precedence over a Demo key, matching pycoingecko.

    Parameters
    ----------
    api_key : str, optional
        Pro API key. Defaults to $COINGECKO_API_KEY. Pass '' to force an
        unauthenticated client regardless of the environment.
    demo_api_key : str, optional
        Demo API key. Defaults to $COINGECKO_DEMO_API_KEY. Pass '' to ignore
        the environment.

    Returns
    -------
    CoinGeckoAPI
        A new client instance.

    Notes
    -----
    Never pass a key as a literal in code that gets committed - export it in
    your shell instead:

        export COINGECKO_DEMO_API_KEY='CG-...'
    """
    api_key = _from_env(API_KEY_ENV) if api_key is None else api_key.strip()
    demo_api_key = _from_env(DEMO_API_KEY_ENV) if demo_api_key is None else demo_api_key.strip()

    return CoinGeckoAPI(api_key=api_key, demo_api_key=demo_api_key)


def describe_credentials():
    """
    Reports which credentials are configured, without revealing them.

    Useful for checking that a key is actually being picked up, since an
    unauthenticated client fails only later, as a rate limit error.

    Returns
    -------
    str
        A short description of the active tier, naming no secret material.
    """
    if _from_env(API_KEY_ENV):
        return f"Pro key found in ${API_KEY_ENV}."
    if _from_env(DEMO_API_KEY_ENV):
        return f"Demo key found in ${DEMO_API_KEY_ENV}."
    return (
        f"No API key configured: using the public endpoint with the strictest "
        f"rate limits. Set ${DEMO_API_KEY_ENV} (free accounts) or "
        f"${API_KEY_ENV} (paid plans)."
    )


def fetch_market_chart(coin_id, vs_currency=DEFAULT_VS_CURRENCY, days=DEFAULT_DAYS,
                       precision=None, client=None):
    """
    Retrieves the raw market chart payload for a single coin.

    Parameters
    ----------
    coin_id : str
        The CoinGecko coin ID (e.g. 'bitcoin').
    vs_currency : str, optional
        The target currency (default: 'usd').
    days : int, optional
        Number of days of data to request (default: 364). Due to free API
        limitations, 364 is the max possible value.
    precision : int or None, optional
        Number of decimal places for price data. When None (default) the API
        returns full precision, which matters for sub-cent coins.
    client : CoinGeckoAPI, optional
        Existing client to reuse. A new one is created when omitted.

    Returns
    -------
    dict
        Raw chart data as returned by the CoinGecko API.

    Raises
    ------
    ValueError
        If the coin id is not a non-empty string, or the API returns no prices.
    """
    if coin_id is None or not isinstance(coin_id, str) or coin_id.strip() == "":
        raise ValueError("A valid coin id must be provided (got None or empty string).")

    client = client or get_client()

    kwargs = {
        'id': coin_id,
        'vs_currency': vs_currency,
        'days': days,
        'interval': INTERVAL,
    }
    # Only forward precision when asked for: the API default is full precision.
    if precision is not None:
        kwargs['precision'] = precision

    raw_chart = client.get_coin_market_chart_by_id(**kwargs)

    if not raw_chart or 'prices' not in raw_chart or len(raw_chart['prices']) == 0:
        raise ValueError(f"No data found for coin id '{coin_id}'.")

    return raw_chart


def fetch_top_coins(limit=5, vs_currency=DEFAULT_VS_CURRENCY, client=None):
    """
    Retrieves the top coins by market cap.

    Parameters
    ----------
    limit : int, optional
        The number of top coins to retrieve (default: 5).
    vs_currency : str, optional
        The currency used to rank market caps (default: 'usd').
    client : CoinGeckoAPI, optional
        Existing client to reuse. A new one is created when omitted.

    Returns
    -------
    list of str
        List of coin IDs sorted by market cap (descending).
        Returns an empty list if the API call fails.
    """
    client = client or get_client()

    try:
        top_coins_by_market_cap = client.get_coins_markets(
            vs_currency=vs_currency,
            order='market_cap_desc',
            per_page=limit,
            page=1,
            sparkline=False
        )
        return [record['id'] for record in top_coins_by_market_cap if record.get('id')]
    except Exception as e:
        print(f"Error retrieving top coins: {e}")
        return []
