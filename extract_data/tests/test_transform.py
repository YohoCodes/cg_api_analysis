"""Tests for extract_data.transform: reshaping raw payloads into DataFrames."""

import datetime as dt
import math
import unittest

import pandas as pd

from ..transform import reformat_data
from .fakes import price_payload


class TestReformatData(unittest.TestCase):
    """Standard cases for reformat_data."""

    def setUp(self):
        self.df = reformat_data(price_payload([100.0, 110.0, 99.0]))

    def test_expected_columns(self):
        self.assertEqual(list(self.df.columns), ['daily_close', 'percent_change'])

    def test_index_is_named_date_and_datetime_typed(self):
        self.assertEqual(self.df.index.name, 'date')
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(self.df.index))

    def test_first_row_dropped_because_percent_change_is_undefined(self):
        # Three prices yield only two defined daily returns.
        self.assertEqual(len(self.df), 2)

    def test_index_sorted_ascending(self):
        self.assertTrue(self.df.index.is_monotonic_increasing)

    def test_last_row_is_today(self):
        self.assertEqual(self.df.index[-1].date(), dt.date.today())

    def test_dates_are_consecutive_days(self):
        gaps = self.df.index.to_series().diff().dropna().unique()
        self.assertEqual(list(gaps), [pd.Timedelta(days=1)])

    def test_close_prices_preserved_in_order(self):
        # The oldest price is consumed by the dropped first row.
        self.assertEqual(self.df['daily_close'].tolist(), [110.0, 99.0])

    def test_percent_change_is_a_percentage(self):
        self.assertAlmostEqual(self.df['percent_change'].iloc[0], 10.0)
        self.assertAlmostEqual(self.df['percent_change'].iloc[1], -10.0)

    def test_ignores_api_timestamps_and_synthesizes_dates(self):
        # Dates are counted back from today rather than read from the payload.
        stale = reformat_data(price_payload([1.0, 2.0], start_ms=0))
        self.assertEqual(stale.index[-1].date(), dt.date.today())


class TestReformatDataEdgeCases(unittest.TestCase):
    """Degenerate payloads that the CoinGecko API can genuinely return."""

    def test_empty_price_list_yields_empty_frame(self):
        df = reformat_data({'prices': []})
        self.assertTrue(df.empty)
        self.assertEqual(list(df.columns), ['daily_close', 'percent_change'])

    def test_single_price_yields_empty_frame(self):
        # One price has no prior day to compare against, so nothing survives.
        self.assertTrue(reformat_data(price_payload([100.0])).empty)

    def test_constant_prices_give_zero_percent_change(self):
        # Stablecoins sit at a fixed peg; returns are defined and zero.
        df = reformat_data(price_payload([1.0, 1.0, 1.0]))
        self.assertEqual(df['percent_change'].tolist(), [0.0, 0.0])

    def test_zero_price_produces_infinite_percent_change(self):
        # A zero close makes the percent change infinite rather than NaN, so it
        # survives dropna and reaches the analysis layer. Pinned deliberately:
        # this is how a rounded-to-zero sub-cent coin corrupts a return series.
        df = reformat_data(price_payload([0.0, 5.0]))
        self.assertEqual(len(df), 1)
        self.assertTrue(math.isinf(df['percent_change'].iloc[0]))

    def test_negative_and_tiny_prices_survive(self):
        # Sub-cent coins must not be rounded away.
        df = reformat_data(price_payload([0.000001, 0.000002]))
        self.assertEqual(df['daily_close'].iloc[0], 0.000002)
        self.assertAlmostEqual(df['percent_change'].iloc[0], 100.0)

    def test_does_not_mutate_input_payload(self):
        payload = price_payload([1.0, 2.0])
        before = [list(pair) for pair in payload['prices']]
        reformat_data(payload)
        self.assertEqual([list(pair) for pair in payload['prices']], before)


if __name__ == '__main__':
    unittest.main()
