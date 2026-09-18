"""Tests for extract_data.market_data: cache-aware retrieval and top-coin caching."""

import datetime as dt
import os
import tempfile
import unittest

from ..market_data import (
    TopCoinsCache,
    clean_coin_ids,
    get_market_chart_table,
    get_market_tables,
)
from ..storage import dataset_path, has_table
from .fakes import FakeCoinGeckoClient, price_payload


class TestCleanCoinIds(unittest.TestCase):
    """Filtering of user-supplied coin ID lists."""

    def test_keeps_valid_ids_in_order(self):
        self.assertEqual(clean_coin_ids(['bitcoin', 'ethereum']), ['bitcoin', 'ethereum'])

    def test_drops_none(self):
        self.assertEqual(clean_coin_ids(['bitcoin', None]), ['bitcoin'])

    def test_drops_empty_and_whitespace_strings(self):
        self.assertEqual(clean_coin_ids(['', '   ', 'bitcoin']), ['bitcoin'])

    def test_drops_non_strings(self):
        self.assertEqual(clean_coin_ids([123, ['bitcoin'], 'bitcoin']), ['bitcoin'])

    def test_empty_list_stays_empty(self):
        self.assertEqual(clean_coin_ids([]), [])

    def test_all_invalid_yields_empty_list(self):
        self.assertEqual(clean_coin_ids([None, '', 42]), [])

    def test_does_not_strip_surrounding_whitespace(self):
        # Padded ids are kept as-is and will fail at the API, not here.
        self.assertEqual(clean_coin_ids([' bitcoin ']), [' bitcoin '])

    def test_duplicates_are_kept(self):
        self.assertEqual(clean_coin_ids(['bitcoin', 'bitcoin']), ['bitcoin', 'bitcoin'])


class TestGetMarketChartTable(unittest.TestCase):
    """Single-coin fetch-and-reshape."""

    def setUp(self):
        self.client = FakeCoinGeckoClient(charts={'bitcoin': price_payload([100.0, 110.0])})

    def test_returns_reformatted_frame(self):
        df = get_market_chart_table('bitcoin', client=self.client)
        self.assertEqual(list(df.columns), ['daily_close', 'percent_change'])
        self.assertEqual(len(df), 1)

    def test_requests_one_extra_day(self):
        # The first day has no percent change, so an extra day is requested to
        # keep the caller's requested window intact.
        get_market_chart_table('bitcoin', days=30, client=self.client)
        self.assertEqual(self.client.chart_calls[0]['days'], 31)


class TestGetMarketTables(unittest.TestCase):
    """Cache-aware multi-coin retrieval."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        # 11 prices comfortably clears the 0.5 * days sufficiency threshold.
        self.client = FakeCoinGeckoClient(charts={
            'bitcoin': price_payload([100.0 + i for i in range(11)]),
            'ethereum': price_payload([50.0 + i for i in range(11)]),
        })

    def fetch(self, coins, **kwargs):
        kwargs.setdefault('days', 10)
        kwargs.setdefault('datasets_dir', self.dir)
        kwargs.setdefault('client', self.client)
        return get_market_tables(coins, **kwargs)

    def test_returns_table_per_coin(self):
        tables, failed = self.fetch(['bitcoin', 'ethereum'])
        self.assertEqual(sorted(tables), ['bitcoin', 'ethereum'])
        self.assertEqual(failed, [])

    def test_writes_csv_to_cache(self):
        self.fetch(['bitcoin'])
        self.assertTrue(has_table(dataset_path('bitcoin', 'usd', 10, datasets_dir=self.dir)))

    def test_second_call_reads_cache_without_calling_api(self):
        self.fetch(['bitcoin'])
        calls_after_first = len(self.client.chart_calls)

        tables, _ = self.fetch(['bitcoin'])
        self.assertEqual(len(self.client.chart_calls), calls_after_first)
        self.assertIn('bitcoin', tables)

    def test_cached_and_fresh_tables_match(self):
        fresh, _ = self.fetch(['bitcoin'])
        cached, _ = self.fetch(['bitcoin'])
        self.assertEqual(
            fresh['bitcoin']['daily_close'].tolist(),
            cached['bitcoin']['daily_close'].tolist()
        )

    def test_overwrite_forces_a_refetch(self):
        self.fetch(['bitcoin'])
        calls_after_first = len(self.client.chart_calls)

        self.fetch(['bitcoin'], overwrite=True)
        self.assertEqual(len(self.client.chart_calls), calls_after_first + 1)

    def test_requests_one_extra_day(self):
        self.fetch(['bitcoin'])
        self.assertEqual(self.client.chart_calls[0]['days'], 11)

    def test_never_sends_precision(self):
        # Cached tables are shared across coins, including sub-cent ones.
        self.fetch(['bitcoin'])
        self.assertNotIn('precision', self.client.chart_calls[0])

    def test_currency_reaches_both_api_and_filename(self):
        self.fetch(['bitcoin'], vs_currency='eur')
        self.assertEqual(self.client.chart_calls[0]['vs_currency'], 'eur')
        self.assertTrue(has_table(dataset_path('bitcoin', 'eur', 10, datasets_dir=self.dir)))

    def test_empty_coin_list(self):
        tables, failed = self.fetch([])
        self.assertEqual(tables, {})
        self.assertEqual(failed, [])


class TestGetMarketTablesFailures(unittest.TestCase):
    """Partial failures must not sink the whole batch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def fetch(self, coins, client, **kwargs):
        kwargs.setdefault('days', 10)
        return get_market_tables(coins, days=kwargs.pop('days'), datasets_dir=self.dir,
                                 client=client, **kwargs)

    def test_api_error_marks_only_that_coin_failed(self):
        client = FakeCoinGeckoClient(charts={
            'bitcoin': price_payload([100.0 + i for i in range(11)]),
            'brokencoin': RuntimeError('429 rate limited'),
        })
        tables, failed = self.fetch(['bitcoin', 'brokencoin'], client)

        self.assertIn('bitcoin', tables)
        self.assertNotIn('brokencoin', tables)
        self.assertEqual(failed, ['brokencoin'])

    def test_later_coins_still_processed_after_a_failure(self):
        client = FakeCoinGeckoClient(charts={
            'brokencoin': RuntimeError('boom'),
            'ethereum': price_payload([50.0 + i for i in range(11)]),
        })
        tables, failed = self.fetch(['brokencoin', 'ethereum'], client)

        self.assertIn('ethereum', tables)
        self.assertEqual(failed, ['brokencoin'])

    def test_insufficient_history_is_a_failure(self):
        # Fewer than 0.5 * days points is treated as too little history.
        client = FakeCoinGeckoClient(charts={'newcoin': price_payload([1.0, 2.0, 3.0, 4.0])})
        tables, failed = self.fetch(['newcoin'], client)

        self.assertEqual(tables, {})
        self.assertEqual(failed, ['newcoin'])

    def test_insufficient_history_is_not_cached(self):
        # A short table must not poison the cache for later runs.
        client = FakeCoinGeckoClient(charts={'newcoin': price_payload([1.0, 2.0, 3.0, 4.0])})
        self.fetch(['newcoin'], client)
        self.assertFalse(has_table(dataset_path('newcoin', 'usd', 10, datasets_dir=self.dir)))

    def test_exactly_half_the_days_is_sufficient(self):
        # The threshold is inclusive: 5 points for days=10.
        client = FakeCoinGeckoClient(charts={'edgecoin': price_payload([1.0, 2.0, 3.0, 4.0, 5.0])})
        tables, failed = self.fetch(['edgecoin'], client)

        self.assertIn('edgecoin', tables)
        self.assertEqual(failed, [])

    def test_empty_price_list_is_a_failure(self):
        client = FakeCoinGeckoClient(charts={'ghost': {'prices': []}})
        tables, failed = self.fetch(['ghost'], client)

        self.assertEqual(tables, {})
        self.assertEqual(failed, ['ghost'])

    def test_invalid_ids_are_skipped_without_calling_api(self):
        client = FakeCoinGeckoClient(charts={})
        tables, failed = self.fetch([None, '', '   '], client)

        self.assertEqual(tables, {})
        self.assertEqual(failed, [None, '', '   '])
        self.assertEqual(client.chart_calls, [])


class TestTopCoinsCache(unittest.TestCase):
    """Day-scoped caching of top-coin lookups."""

    def setUp(self):
        self.client = FakeCoinGeckoClient(markets=[{'id': 'bitcoin'}, {'id': 'ethereum'}])
        self.cache = TopCoinsCache(client=self.client)

    def test_first_call_hits_the_api(self):
        self.assertEqual(self.cache.get(limit=2), ['bitcoin', 'ethereum'])
        self.assertEqual(len(self.client.market_calls), 1)

    def test_repeat_call_same_day_uses_cache(self):
        self.cache.get(limit=2)
        self.cache.get(limit=2)
        self.assertEqual(len(self.client.market_calls), 1)

    def test_different_limit_refetches(self):
        self.cache.get(limit=2)
        self.cache.get(limit=5)
        self.assertEqual(len(self.client.market_calls), 2)

    def test_stale_cache_refetches(self):
        self.cache.get(limit=2)
        self.cache.date_of_save = dt.date.today() - dt.timedelta(days=1)

        self.cache.get(limit=2)
        self.assertEqual(len(self.client.market_calls), 2)

    def test_records_cache_metadata(self):
        self.cache.get(limit=2)
        self.assertEqual(self.cache.date_of_save, dt.date.today())
        self.assertEqual(self.cache.last_limit, 2)

    def test_api_failure_returns_empty_list(self):
        cache = TopCoinsCache(client=FakeCoinGeckoClient(markets=RuntimeError('boom')))
        self.assertEqual(cache.get(limit=2), [])

    def test_api_failure_is_not_cached(self):
        # A transient failure must not block retrying for the rest of the day.
        client = FakeCoinGeckoClient(markets=RuntimeError('boom'))
        cache = TopCoinsCache(client=client)

        cache.get(limit=2)
        cache.get(limit=2)
        self.assertEqual(len(client.market_calls), 2)

    def test_forwards_vs_currency(self):
        cache = TopCoinsCache(vs_currency='eur', client=self.client)
        cache.get(limit=2)
        self.assertEqual(self.client.market_calls[0]['vs_currency'], 'eur')


if __name__ == '__main__':
    unittest.main()
