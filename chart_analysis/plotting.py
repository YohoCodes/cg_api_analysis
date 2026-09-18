# Price chart plotting for market chart tables.

import matplotlib.pyplot as plt


def plot_price(df, coin_id, vs_currency='usd', ax=None):
    """
    Plots one coin's daily close prices.

    Parameters
    ----------
    df : pd.DataFrame
        Market chart table indexed by date, with a 'daily_close' column.
    coin_id : str
        Coin ID, used for the chart title.
    vs_currency : str, optional
        Currency the prices are denominated in (default: 'usd').
    ax : matplotlib.axes.Axes, optional
        Axes to draw on. A new figure is created when omitted.

    Returns
    -------
    matplotlib.axes.Axes
        The axes the chart was drawn on.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df.index, df['daily_close'], marker='o')
    ax.set_title(f"{coin_id.capitalize()} Price Chart")
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Price ({vs_currency.upper()})")
    ax.grid()

    return ax


def plot_prices(tables, vs_currency='usd', coin_ids=None, show=True):
    """
    Plots the price chart for one or more coins, one subplot per coin.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    vs_currency : str, optional
        Currency the prices are denominated in (default: 'usd').
    coin_ids : list of str, optional
        Coins to plot, in order. Defaults to every key in `tables`.
    show : bool, optional
        Whether to call plt.show() (default: True).

    Returns
    -------
    matplotlib.figure.Figure
        The figure holding the chart(s).

    Raises
    ------
    ValueError
        If no coins were given, or a requested coin has no table.
    """
    coin_ids = list(tables.keys()) if coin_ids is None else coin_ids

    if not coin_ids:
        raise ValueError(
            "No coins to plot: `tables` is empty and no `coin_ids` were given. "
            "Retrieve the data first, e.g. extract_data.get_market_tables([...]), "
            "and check its `failed` list if you expected coins to be there."
        )

    missing = [coin for coin in coin_ids if coin not in tables]
    if missing:
        raise ValueError(
            f"No table to plot for: {', '.join(map(str, missing))}. "
            f"Available coins: {', '.join(tables) or 'none'}."
        )

    num_coins = len(coin_ids)
    fig, axes = plt.subplots(num_coins, 1, figsize=(12, 5 * num_coins), sharex=False)
    if num_coins == 1:
        axes = [axes]  # Make axes iterable if only one coin

    for ax, coin in zip(axes, coin_ids):
        plot_price(tables[coin], coin, vs_currency=vs_currency, ax=ax)

    plt.tight_layout()
    if show:
        plt.show()

    return fig
