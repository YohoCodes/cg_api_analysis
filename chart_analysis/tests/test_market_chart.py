"""
Tests for the analyze_coin_market_chart facade.

The class is exercised with an injected fake client and a temporary datasets
directory, so no test reaches the network or touches the real cache.
"""

import os
import tempfile
import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from extract_data.tests.fakes import FakeCoinGeckoClient, price_payload

from ..market_chart import analyze_coin_market_chart


def rising(n, start=100.0):
    """Builds a payload of n steadily rising prices."""
    return price_payload([start + i for i in range(n)])


class FacadeTestCase(unittest.TestCase):
    """Gives every test its own cache directory and fake client."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(plt.close, 'all')

        self.client = FakeCoinGeckoClient(
            charts={
                'bitcoin': rising(11, 100.0),
                'ethereum': rising(11, 50.0),
                'litecoin': rising(11, 10.0),
            },
            markets=[{'id': 'bitcoin'}, {'id': 'ethereum'}],
        )

    def build(self, **kwargs):
        """Constructs the class with the test's fake client and temp cache."""
        kwargs.setdefault('days', 10)
        kwargs.setdefault('datasets_dir', self.tmp.name)
        kwargs.setdefault('client', self.client)
        return analyze_coin_market_chart(**kwargs)


class TestSingleCoin(FacadeTestCase):
    """Constructing with a single coin ID."""

    def test_stores_raw_chart(self):
        chart = self.build(id='bitcoin')
        self.assertIn('prices', chart.raw_chart)
        self.assertTrue(chart.is_saved)

    def test_reformat_data_uses_stored_chart(self):
        df = self.build(id='bitcoin').reformat_data()
        self.assertEqual(list(df.columns), ['daily_close', 'percent_change'])

    def test_requests_full_precision_by_default(self):
        # Sending a precision rounds sub-cent coins to zero.
        self.build(id='bitcoin')
        self.assertNotIn('precision', self.client.chart_calls[0])

    def test_precision_is_opt_in(self):
        self.build(id='bitcoin', precision=2)
        self.assertEqual(self.client.chart_calls[0]['precision'], 2)

    def test_requests_one_extra_day(self):
        self.build(id='bitcoin', days=30)
        self.assertEqual(self.client.chart_calls[0]['days'], 31)

    def test_correlation_returns_none_for_one_coin(self):
        chart = self.build(id='bitcoin')
        self.assertIsNone(chart.price_correlation())
        self.assertIsNone(chart.return_correlation())

    def test_invalid_id_raises(self):
        for bad in (None, '', '   '):
            with self.assertRaises(ValueError):
                self.build(id=bad)

    def test_api_failure_raises_value_error(self):
        client = FakeCoinGeckoClient(charts={'bitcoin': RuntimeError('429 rate limited')})
        with self.assertRaises(ValueError):
            self.build(id='bitcoin', client=client)

    def test_single_coin_plot(self):
        self.build(id='bitcoin').plot()
        self.assertEqual(len(plt.get_fignums()), 1)


class TestMultipleCoins(FacadeTestCase):
    """Constructing with a list of coin IDs."""

    def test_saves_a_table_per_coin(self):
        chart = self.build(id=['bitcoin', 'ethereum'])
        self.assertEqual(sorted(chart.saved_tables), ['bitcoin', 'ethereum'])
        self.assertTrue(chart.is_saved)

    def test_writes_csvs_to_the_given_directory(self):
        self.build(id=['bitcoin'])
        self.assertIn('bitcoin_usd_10days.csv', os.listdir(self.tmp.name))

    def test_correlations_cover_every_pair(self):
        chart = self.build(id=['bitcoin', 'ethereum', 'litecoin'])
        self.assertEqual(len(chart.price_correlation()), 3)
        self.assertEqual(len(chart.return_correlation()), 3)

    def test_invalid_ids_are_filtered_out(self):
        chart = self.build(id=['bitcoin', None, '', 'ethereum'])
        self.assertEqual(chart.id, ['bitcoin', 'ethereum'])

    def test_all_invalid_ids_raise(self):
        with self.assertRaises(ValueError):
            self.build(id=[None, '', 42])

    def test_empty_list_raises(self):
        with self.assertRaises(ValueError):
            self.build(id=[])

    def test_failed_coins_are_dropped_from_id(self):
        # Surviving coins only: a failed coin must not linger and break the
        # correlation pairing.
        self.client.charts['brokencoin'] = RuntimeError('boom')
        chart = self.build(id=['bitcoin', 'brokencoin', 'ethereum'])

        self.assertEqual(chart.id, ['bitcoin', 'ethereum'])
        self.assertNotIn('brokencoin', chart.saved_tables)

    def test_correlation_excludes_failed_coins(self):
        self.client.charts['brokencoin'] = RuntimeError('boom')
        chart = self.build(id=['bitcoin', 'brokencoin', 'ethereum'])

        result = chart.price_correlation()
        self.assertEqual(len(result), 1)
        self.assertNotIn('brokencoin', result[['coin1', 'coin2']].to_numpy())

    def test_multi_coin_plot_has_one_subplot_per_coin(self):
        chart = self.build(id=['bitcoin', 'ethereum'])
        chart.plot()
        self.assertEqual(len(plt.gcf().axes), 2)


class TestCaching(FacadeTestCase):
    """Disk cache and in-memory cache behavior."""

    def test_second_instance_reads_the_cache(self):
        self.build(id=['bitcoin'])
        calls = len(self.client.chart_calls)

        self.build(id=['bitcoin'])
        self.assertEqual(len(self.client.chart_calls), calls)

    def test_overwrite_refetches(self):
        self.build(id=['bitcoin'])
        calls = len(self.client.chart_calls)

        self.build(id=['bitcoin'], overwrite=True)
        self.assertEqual(len(self.client.chart_calls), calls + 1)

    def test_save_tables_skips_when_already_saved(self):
        chart = self.build(id=['bitcoin'])
        chart.saved_tables = {'sentinel': None}

        chart.save_tables(['bitcoin'])
        self.assertEqual(chart.saved_tables, {'sentinel': None})

    def test_reset_rebuilds_saved_tables(self):
        chart = self.build(id=['bitcoin'], reset=True)
        chart.saved_tables = {'sentinel': None}

        chart.save_tables(['bitcoin'])
        self.assertEqual(list(chart.saved_tables), ['bitcoin'])

    def test_reuses_the_injected_client(self):
        self.assertIs(self.build(id=['bitcoin']).cg, self.client)

    def test_default_datasets_dir_is_not_touched(self):
        chart = self.build(id=['bitcoin'])
        self.assertEqual(chart.datasets_dir, self.tmp.name)


class TestTopCoins(FacadeTestCase):
    """The limit parameter and top_coins method."""

    def test_limit_replaces_the_id_list(self):
        chart = self.build(id='ignored', limit=2)
        self.assertEqual(chart.id, ['bitcoin', 'ethereum'])

    def test_limit_forwards_to_the_api(self):
        self.build(limit=2)
        self.assertEqual(self.client.market_calls[0]['per_page'], 2)

    def test_top_coins_is_callable_twice(self):
        # Regression: the method used to overwrite itself with its own result,
        # so the second call raised TypeError: 'list' object is not callable.
        chart = self.build(id=['bitcoin'])
        self.assertEqual(chart.top_coins(limit=2), ['bitcoin', 'ethereum'])
        self.assertEqual(chart.top_coins(limit=2), ['bitcoin', 'ethereum'])

    def test_repeat_top_coins_call_is_cached(self):
        chart = self.build(id=['bitcoin'])
        chart.top_coins(limit=2)
        chart.top_coins(limit=2)
        self.assertEqual(len(self.client.market_calls), 1)

    def test_top_coins_failure_raises_no_valid_ids(self):
        # An empty top-coin list leaves nothing to analyze.
        client = FakeCoinGeckoClient(charts={}, markets=RuntimeError('boom'))
        with self.assertRaises(ValueError):
            self.build(limit=5, client=client)


class TestAttributes(FacadeTestCase):
    """Constructor wiring."""

    def test_defaults(self):
        chart = self.build(id='bitcoin')
        self.assertEqual(chart.vs_currency, 'usd')
        self.assertEqual(chart.interval, 'daily')
        self.assertIsNone(chart.precision)
        self.assertFalse(chart.overwrite)

    def test_currency_reaches_api_and_filename(self):
        chart = self.build(id=['bitcoin'], vs_currency='eur')
        self.assertEqual(chart.vs_currency, 'eur')
        self.assertIn('bitcoin_eur_10days.csv', os.listdir(self.tmp.name))


if __name__ == '__main__':
    unittest.main()
