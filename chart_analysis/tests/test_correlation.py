"""
Tests for chart_analysis.correlation.

Pearson correlation is undefined for a zero-variance series, and pandas/numpy are
known to answer inconsistently there (NaN, or a spurious +-1 from floating-point
residuals). These tests therefore pin what the pipeline does with such pairs
rather than what corr() returns for them.
"""

import unittest

import numpy as np
import pandas as pd

from ..correlation import price_correlation, return_correlation
from .helpers import capture, make_table, make_tables


class TestCorrelationShape(unittest.TestCase):
    """Result shape and ordering, shared by both correlation functions."""

    def setUp(self):
        self.tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0, 130.0],
            'ethereum': [50.0, 55.0, 60.0, 65.0],
            'litecoin': [10.0, 9.0, 8.0, 7.0],
        })

    def test_columns(self):
        result = price_correlation(self.tables)
        self.assertEqual(list(result.columns), ['coin1', 'coin2', 'correlation'])

    def test_one_row_per_unique_pair(self):
        # Three coins give three pairs, not six: order within a pair is ignored.
        self.assertEqual(len(price_correlation(self.tables)), 3)

    def test_pairs_are_unordered_and_unique(self):
        result = price_correlation(self.tables)
        pairs = {frozenset([row.coin1, row.coin2]) for row in result.itertuples()}
        self.assertEqual(len(pairs), 3)

    def test_no_coin_paired_with_itself(self):
        result = price_correlation(self.tables)
        self.assertFalse((result['coin1'] == result['coin2']).any())

    def test_sorted_by_correlation_descending(self):
        result = price_correlation(self.tables)
        self.assertTrue(result['correlation'].is_monotonic_decreasing)

    def test_index_is_reset(self):
        result = price_correlation(self.tables)
        self.assertEqual(result.index.tolist(), list(range(len(result))))

    def test_correlations_within_valid_range(self):
        result = price_correlation(self.tables)
        self.assertTrue(result['correlation'].between(-1.0, 1.0).all())


class TestPriceCorrelationValues(unittest.TestCase):
    """Correlation of daily close prices."""

    def test_identical_series_correlate_perfectly(self):
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [1.0, 2.0, 3.0, 4.0]})
        self.assertAlmostEqual(price_correlation(tables)['correlation'].iloc[0], 1.0)

    def test_scaled_series_correlate_perfectly(self):
        # Correlation is scale-invariant: price level must not matter.
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [100.0, 200.0, 300.0, 400.0]})
        self.assertAlmostEqual(price_correlation(tables)['correlation'].iloc[0], 1.0)

    def test_mirrored_series_correlate_negatively(self):
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [4.0, 3.0, 2.0, 1.0]})
        self.assertAlmostEqual(price_correlation(tables)['correlation'].iloc[0], -1.0)

    def test_uses_close_prices_not_returns(self):
        # These two rise together in price while their daily returns diverge,
        # so price and return correlation must disagree.
        tables = make_tables({'a': [100.0, 101.0, 130.0, 131.0], 'b': [10.0, 13.0, 13.1, 17.0]})
        price = price_correlation(tables)['correlation'].iloc[0]
        returns = return_correlation(tables)['correlation'].iloc[0]
        self.assertNotAlmostEqual(price, returns)


class TestReturnCorrelationValues(unittest.TestCase):
    """Correlation of daily returns."""

    def test_identical_returns_correlate_perfectly(self):
        # Returns must vary: a constant return series has zero variance and is
        # dropped as undefined (see TestDegenerateSeries).
        tables = make_tables({'a': [100.0, 110.0, 99.0, 118.8],
                              'b': [1.0, 1.1, 0.99, 1.188]})
        self.assertAlmostEqual(return_correlation(tables)['correlation'].iloc[0], 1.0)

    def test_uses_percent_change_column(self):
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [4.0, 3.0, 2.0, 1.0]})
        expected = tables['a']['percent_change'].corr(tables['b']['percent_change'])
        self.assertAlmostEqual(return_correlation(tables)['correlation'].iloc[0], expected)


class TestCoinSelection(unittest.TestCase):
    """The coin_ids argument."""

    def setUp(self):
        self.tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0, 130.0],
            'ethereum': [50.0, 55.0, 60.0, 65.0],
            'litecoin': [10.0, 9.0, 8.0, 7.0],
        })

    def test_defaults_to_every_table(self):
        self.assertEqual(len(price_correlation(self.tables)), 3)

    def test_subset_limits_the_pairs(self):
        result = price_correlation(self.tables, coin_ids=['bitcoin', 'ethereum'])
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result.iloc[0][['coin1', 'coin2']]), {'bitcoin', 'ethereum'})

    def test_extra_tables_do_not_leak_into_results(self):
        result = price_correlation(self.tables, coin_ids=['bitcoin', 'ethereum'])
        self.assertNotIn('litecoin', result[['coin1', 'coin2']].to_numpy())


class TestTooFewCoins(unittest.TestCase):
    """Correlation needs at least two coins."""

    def test_single_coin_returns_none(self):
        self.assertIsNone(price_correlation(make_tables({'bitcoin': [1.0, 2.0, 3.0]})))

    def test_single_coin_returns_none_for_returns(self):
        self.assertIsNone(return_correlation(make_tables({'bitcoin': [1.0, 2.0, 3.0]})))

    def test_empty_tables_returns_none(self):
        self.assertIsNone(price_correlation({}))

    def test_subset_of_one_returns_none(self):
        tables = make_tables({'a': [1.0, 2.0, 3.0], 'b': [3.0, 2.0, 1.0]})
        self.assertIsNone(price_correlation(tables, coin_ids=['a']))


class TestDateAlignment(unittest.TestCase):
    """Coins listed on different dates, or with gaps, must stay aligned."""

    def test_uses_the_overlapping_window(self):
        # 'b' starts two days later; only the shared dates should be compared.
        tables = {
            'a': make_table([1.0, 2.0, 3.0, 4.0, 5.0], start='2024-01-01'),
            'b': make_table([9.0, 8.0, 7.0], start='2024-01-03'),
        }
        result = price_correlation(tables)
        self.assertEqual(len(result), 1)
        self.assertTrue(np.isfinite(result['correlation'].iloc[0]))

    def test_alignment_is_symmetric(self):
        # The join starts from the first table, so a shorter first coin must not
        # silently change the answer.
        long = make_table([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], start='2024-01-01')
        short = make_table([1.0, 2.0, 3.0, 4.0], start='2024-01-01')

        forward = price_correlation({'a': short, 'b': long})['correlation'].iloc[0]
        backward = price_correlation({'b': long, 'a': short})['correlation'].iloc[0]
        self.assertAlmostEqual(forward, backward)

    def test_non_overlapping_dates_return_none(self):
        # No shared dates means no defined correlation at all.
        result, _ = capture(price_correlation, self.disjoint_tables())
        self.assertIsNone(result)

    def test_non_overlapping_dates_explain_the_problem(self):
        _, output = capture(price_correlation, self.disjoint_tables())
        self.assertIn('shared dates', output)
        self.assertIn('0 in common', output)

    def test_non_overlapping_dates_report_each_date_range(self):
        # The ranges are what tell the caller which coin is the odd one out.
        _, output = capture(price_correlation, self.disjoint_tables())
        self.assertIn('2024-01-02', output)
        self.assertIn('2025-06-02', output)

    def test_non_overlapping_dates_suggest_a_remedy(self):
        _, output = capture(price_correlation, self.disjoint_tables())
        self.assertIn('overwrite=True', output)

    def test_single_shared_date_is_insufficient(self):
        # One shared row cannot define a correlation either.
        tables = {
            'a': make_table([1.0, 2.0, 3.0, 4.0], start='2024-01-01'),   # 01-02..01-04
            'b': make_table([1.0, 2.0, 3.0], start='2024-01-03'),        # 01-04..01-05
        }
        result, output = capture(price_correlation, tables)
        self.assertIsNone(result)
        self.assertIn('1 in common', output)

    @staticmethod
    def disjoint_tables():
        """Two coins whose date ranges do not overlap at all."""
        return {
            'a': make_table([1.0, 2.0, 3.0, 4.0], start='2024-01-01'),
            'b': make_table([1.0, 2.0, 3.0, 4.0], start='2025-06-01'),
        }

    def test_rows_with_missing_data_are_excluded(self):
        # A NaN close in one coin must drop that date for every coin.
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [2.0, 4.0, 6.0, 8.0]})
        tables['b'].iloc[1, tables['b'].columns.get_loc('daily_close')] = np.nan

        result = price_correlation(tables)
        self.assertTrue(np.isfinite(result['correlation'].iloc[0]))


class TestDegenerateSeries(unittest.TestCase):
    """
    Zero-variance and non-finite series.

    Stablecoins are the real-world case: a coin pegged flat has no variance, so
    its correlation is mathematically undefined.
    """

    def test_flat_series_pair_leaves_nothing_to_rank(self):
        # A pegged coin correlates with nothing, so the only pair is undefined.
        tables = make_tables({'volatile': [1.0, 2.0, 3.0, 4.0], 'pegged': [1.0, 1.0, 1.0, 1.0]})
        result, _ = capture(price_correlation, tables)
        self.assertIsNone(result)

    def test_flat_pair_does_not_hide_valid_pairs(self):
        tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0, 130.0],
            'ethereum': [50.0, 55.0, 60.0, 65.0],
            'tether': [1.0, 1.0, 1.0, 1.0],
        })
        result, _ = capture(price_correlation, tables)

        self.assertEqual(len(result), 1)
        self.assertEqual(set(result.iloc[0][['coin1', 'coin2']]), {'bitcoin', 'ethereum'})

    def test_no_nan_correlations_reach_the_caller(self):
        tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0, 130.0],
            'ethereum': [50.0, 55.0, 60.0, 65.0],
            'tether': [1.0, 1.0, 1.0, 1.0],
        })
        result, _ = capture(price_correlation, tables)
        self.assertFalse(result['correlation'].isna().any())

    def test_all_pairs_undefined_returns_none(self):
        tables = make_tables({'tether': [1.0, 1.0, 1.0], 'usd-coin': [1.0, 1.0, 1.0]})
        result, output = capture(price_correlation, tables)
        self.assertIsNone(result)
        self.assertIn('No coin pair has a defined correlation', output)

    def test_infinite_returns_do_not_crash(self):
        # A zero close produces an infinite percent change upstream.
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [1.0, 2.0, 3.0, 4.0]})
        tables['b'].iloc[0, tables['b'].columns.get_loc('percent_change')] = np.inf

        result = return_correlation(tables)
        self.assertIsNotNone(result)

    def test_two_row_series_still_correlate(self):
        # The smallest input that yields a defined correlation.
        tables = make_tables({'a': [1.0, 2.0, 3.0], 'b': [5.0, 6.0, 7.0]})
        result = price_correlation(tables)
        self.assertEqual(len(result), 1)


class TestRemediationGuidance(unittest.TestCase):
    """
    Dropped pairs must explain themselves.

    A silently shorter ranking is the failure mode these messages exist to prevent.
    """

    def setUp(self):
        self.tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0, 130.0],
            'ethereum': [50.0, 55.0, 60.0, 65.0],
            'tether': [1.0, 1.0, 1.0, 1.0],
            'usd-coin': [1.0, 1.0, 1.0, 1.0],
        })

    def test_reports_how_many_pairs_were_dropped(self):
        _, output = capture(price_correlation, self.tables)
        self.assertIn('5 of 6', output)

    def test_names_the_constant_coins(self):
        _, output = capture(price_correlation, self.tables)
        self.assertIn('tether', output)
        self.assertIn('usd-coin', output)

    def test_explains_why_constant_coins_are_undefined(self):
        _, output = capture(price_correlation, self.tables)
        self.assertIn('zero variance', output)
        self.assertIn('stablecoin', output)

    def test_suggests_a_remedy(self):
        _, output = capture(price_correlation, self.tables)
        self.assertIn('To fix:', output)

    def test_does_not_blame_healthy_coins(self):
        # A healthy coin appears in a dropped pair only because its partner was
        # degenerate; naming it would send the caller after the wrong coin.
        _, output = capture(price_correlation, self.tables)
        blamed = output.split('zero variance):')[1].splitlines()[0]
        self.assertNotIn('bitcoin', blamed)
        self.assertNotIn('ethereum', blamed)

    def test_reports_non_finite_coins_separately(self):
        tables = make_tables({
            'a': [1.0, 2.0, 3.0, 4.0],
            'b': [2.0, 4.0, 6.0, 8.0],
            'shiba-inu': [1.0, 2.0, 3.0, 4.0],
        })
        # A zero close upstream leaves an infinite return behind.
        column = tables['shiba-inu'].columns.get_loc('percent_change')
        tables['shiba-inu'].iloc[:, column] = [np.inf, np.nan, np.inf]

        _, output = capture(return_correlation, tables)
        self.assertIn('infinite or missing', output)
        self.assertIn('precision=None', output)

    def test_stays_quiet_when_every_pair_is_defined(self):
        healthy = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [4.0, 3.0, 2.0, 1.0]})
        _, output = capture(price_correlation, healthy)
        self.assertEqual(output, '')

    def test_singular_phrasing_for_one_dropped_pair(self):
        tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0, 130.0],
            'ethereum': [50.0, 55.0, 60.0, 65.0],
            'tether': [1.0, 1.0, 1.0, 1.0],
        })
        _, output = capture(price_correlation, tables)
        self.assertIn('2 of 3 coin pairs have', output)


class TestInputIsNotMutated(unittest.TestCase):
    """Analysis must leave the caller's tables untouched."""

    def test_tables_unchanged(self):
        tables = make_tables({'a': [1.0, 2.0, 3.0, 4.0], 'b': [4.0, 3.0, 2.0, 1.0]})
        before = {coin: df.copy() for coin, df in tables.items()}

        price_correlation(tables)
        return_correlation(tables)

        for coin, df in before.items():
            pd.testing.assert_frame_equal(tables[coin], df)


if __name__ == '__main__':
    unittest.main()
