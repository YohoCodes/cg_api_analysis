# Pairwise correlation analysis over market chart tables.

from itertools import combinations

import numpy as np
import pandas as pd


def _combine_column(tables, column):
    """
    Joins one column from every coin's table into a single DataFrame.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    column : str
        Column to pull from each table ('daily_close' or 'percent_change').

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date with one column per coin, rows containing
        any NaN dropped so the coins stay aligned.
    """
    combined = None
    for coin_id, table in tables.items():
        slice = table[[column]].rename(columns={column: coin_id})
        # First iteration creates the initial dataframe, the rest join onto it
        combined = slice if combined is None else combined.join(slice)

    # Drop rows with any NaN to ensure proper alignment
    return combined.dropna()


def _date_range_summary(tables, coin_ids):
    """
    Describes each coin's available date range, for diagnostics.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    coin_ids : list of str
        Coins to describe.

    Returns
    -------
    str
        One indented 'coin: first to last' line per coin.
    """
    lines = []
    for coin in coin_ids:
        index = tables[coin].index
        if len(index) == 0:
            lines.append(f"    {coin}: no data")
        else:
            lines.append(f"    {coin}: {index[0].date()} to {index[-1].date()}")
    return "\n".join(lines)


def _insufficient_overlap_message(tables, coin_ids, shared_days):
    """
    Explains that the coins share too few dates to correlate, and how to fix it.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    coin_ids : list of str
        Coins that were compared.
    shared_days : int
        Number of dates common to every coin.

    Returns
    -------
    str
        A message naming the problem, the date ranges, and the remedy.
    """
    return (
        f"Correlation needs at least two shared dates, but these coins have "
        f"{shared_days} in common.\n"
        f"  Date range held for each coin:\n"
        f"{_date_range_summary(tables, coin_ids)}\n"
        f"  To fix: retrieve every coin with the same 'days' window, and delete any\n"
        f"  stale CSVs in datasets/ (or pass overwrite=True) so the cached tables\n"
        f"  cover the same period. Newly listed coins may simply lack the history."
    )


def _undefined_pairs_message(combined, dropped_pairs, total_pairs):
    """
    Explains why some coin pairs have an undefined correlation, and how to fix it.

    Correlation is undefined when a series never varies (zero variance) or holds
    non-finite values, so those pairs are dropped from the ranking instead of being
    reported as NaN.

    Parameters
    ----------
    combined : pd.DataFrame
        The aligned DataFrame with one column per coin.
    dropped_pairs : pd.DataFrame
        The rows removed from the ranking, with 'coin1' and 'coin2' columns.
    total_pairs : int
        How many pairs were evaluated in total.

    Returns
    -------
    str
        A message naming the offending coins and the remedy for each cause.
    """
    involved = set(dropped_pairs['coin1']) | set(dropped_pairs['coin2'])

    # Only the coin that is itself degenerate is at fault: a healthy coin shows up
    # here merely because it was paired with a degenerate one.
    # Non-finite is checked first: an all-infinite column is constant too, but
    # "contains infinity" is the specific, actionable diagnosis.
    non_finite = sorted(coin for coin in involved if not np.isfinite(combined[coin]).all())
    flat = sorted(coin for coin in involved
                  if coin not in non_finite and combined[coin].nunique() <= 1)

    dropped_count = len(dropped_pairs)
    plural = "pair has" if dropped_count == 1 else "pairs have"
    lines = [
        f"Note: {dropped_count} of {total_pairs} coin {plural} an undefined "
        f"correlation and was left out of the ranking."
        if dropped_count == 1 else
        f"Note: {dropped_count} of {total_pairs} coin {plural} an undefined "
        f"correlation and were left out of the ranking."
    ]

    if flat:
        lines.append(
            f"  Constant over this window (zero variance): {', '.join(flat)}\n"
            f"    A value that never moves has no correlation with anything - this is\n"
            f"    normal for stablecoins pegged to a currency. To fix: drop these coins\n"
            f"    from the analysis, or use a window long enough for the peg to move."
        )

    if non_finite:
        lines.append(
            f"  Holds infinite or missing values: {', '.join(non_finite)}\n"
            f"    Usually a close price of 0, which makes the percent change infinite.\n"
            f"    To fix: re-retrieve the coin with overwrite=True and precision=None,\n"
            f"    so sub-cent prices are not rounded down to zero."
        )

    # A dropped pair where neither coin is degenerate has no explanation above.
    degenerate = set(flat) | set(non_finite)
    unexplained = dropped_pairs[~dropped_pairs['coin1'].isin(degenerate)
                                & ~dropped_pairs['coin2'].isin(degenerate)]
    if not unexplained.empty:
        named = ', '.join(f"{row.coin1}/{row.coin2}" for row in unexplained.itertuples())
        lines.append(f"  Undefined for another reason: {named}")

    return "\n".join(lines)


def _rank_pairs(combined, coin_ids):
    """
    Ranks every coin pair by correlation, separating out the undefined ones.

    Parameters
    ----------
    combined : pd.DataFrame
        DataFrame with one column per coin, as built by _combine_column.
    coin_ids : list of str
        Coin IDs to pair up.

    Returns
    -------
    tuple of (pd.DataFrame, pd.DataFrame)
        - the defined pairs, sorted by correlation (descending), index reset
        - the pairs whose correlation was undefined (NaN)
    """
    corr_matrix = combined.corr()

    # Save all unique combinations of coin ids
    data = []
    for coin1, coin2 in combinations(coin_ids, 2):
        data.append({'coin1': coin1, 'coin2': coin2, 'correlation': corr_matrix.at[coin1, coin2]})

    all_pairs = pd.DataFrame(data, columns=['coin1', 'coin2', 'correlation'])

    undefined = all_pairs[all_pairs['correlation'].isna()]
    ranking = all_pairs.dropna(subset=['correlation'])
    ranking = ranking.sort_values(by=['correlation'], ascending=False).reset_index(drop=True)

    return ranking, undefined


def _correlate(tables, coin_ids, column):
    """
    Shared implementation behind price_correlation and return_correlation.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    coin_ids : list of str or None
        Coins to include. Defaults to every key in `tables`.
    column : str
        Column to correlate ('daily_close' or 'percent_change').

    Returns
    -------
    pd.DataFrame or None
        DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair
        with a defined correlation, sorted descending. Returns None when no pair
        could be computed, after printing why.
    """
    coin_ids = list(tables.keys()) if coin_ids is None else coin_ids

    # Correlation is not defined for a single coin
    if len(coin_ids) < 2:
        print("Correlation analysis requires at least two coins.")
        return None

    combined = _combine_column({coin: tables[coin] for coin in coin_ids}, column)

    # Coins whose date ranges barely overlap cannot be compared
    if len(combined) < 2:
        print(_insufficient_overlap_message(tables, coin_ids, len(combined)))
        return None

    total_pairs = len(combined.columns) * (len(combined.columns) - 1) // 2
    ranking, undefined = _rank_pairs(combined, coin_ids)

    if not undefined.empty:
        print(_undefined_pairs_message(combined, undefined, total_pairs))

    # Every pair was undefined, so there is nothing to rank
    if ranking.empty:
        print("No coin pair has a defined correlation over this window.")
        return None

    return ranking


def price_correlation(tables, coin_ids=None):
    """
    Computes the correlation of daily close prices between all pairs of coins.

    Pairs whose correlation is undefined - a coin that never varies, or one holding
    non-finite values - are left out of the ranking, and an explanation naming the
    coins and the remedy is printed.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    coin_ids : list of str, optional
        Coins to include. Defaults to every key in `tables`.

    Returns
    -------
    pd.DataFrame or None
        DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair
        with a defined correlation, sorted by correlation (descending). Returns None
        if fewer than two coins were given, if they share fewer than two dates, or if
        no pair has a defined correlation; the reason is printed in each case.
    """
    return _correlate(tables, coin_ids, 'daily_close')


def return_correlation(tables, coin_ids=None):
    """
    Computes the correlation of percent changes (daily returns) between all pairs of coins.

    Pairs whose correlation is undefined - a coin that never varies, or one holding
    non-finite values - are left out of the ranking, and an explanation naming the
    coins and the remedy is printed.

    Parameters
    ----------
    tables : dict
        Mapping of coin ID to its market chart DataFrame.
    coin_ids : list of str, optional
        Coins to include. Defaults to every key in `tables`.

    Returns
    -------
    pd.DataFrame or None
        DataFrame with columns ['coin1', 'coin2', 'correlation'] for each coin pair
        with a defined correlation, sorted by correlation (descending). Returns None
        if fewer than two coins were given, if they share fewer than two dates, or if
        no pair has a defined correlation; the reason is printed in each case.
    """
    return _correlate(tables, coin_ids, 'percent_change')
