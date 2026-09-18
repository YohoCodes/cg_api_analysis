"""Tests for extract_data.client: argument forwarding and input validation."""

import os
import unittest
from unittest import mock

from ..client import (
    API_KEY_ENV,
    DEMO_API_KEY_ENV,
    INTERVAL,
    describe_credentials,
    fetch_market_chart,
    fetch_top_coins,
    get_client,
)
from .fakes import FakeCoinGeckoClient, price_payload


def with_env(**variables):
    """Patches the credential variables, clearing any the caller omits."""
    environment = {API_KEY_ENV: '', DEMO_API_KEY_ENV: ''}
    environment.update(variables)
    return mock.patch.dict(os.environ, environment, clear=False)


class TestFetchMarketChart(unittest.TestCase):
    """Standard and edge cases for fetch_market_chart."""

    def setUp(self):
        self.payload = price_payload([100.0, 110.0, 120.0])
        self.client = FakeCoinGeckoClient(charts={'bitcoin': self.payload})

    def test_returns_payload_unchanged(self):
        result = fetch_market_chart('bitcoin', client=self.client)
        self.assertEqual(result, self.payload)

    def test_forwards_arguments_to_api(self):
        fetch_market_chart('bitcoin', vs_currency='eur', days=30, client=self.client)

        call = self.client.chart_calls[0]
        self.assertEqual(call['id'], 'bitcoin')
        self.assertEqual(call['vs_currency'], 'eur')
        self.assertEqual(call['days'], 30)

    def test_always_requests_daily_interval(self):
        # Hourly data is enterprise-only, so the interval is not configurable.
        fetch_market_chart('bitcoin', client=self.client)
        self.assertEqual(self.client.chart_calls[0]['interval'], INTERVAL)
        self.assertEqual(INTERVAL, 'daily')

    def test_precision_omitted_by_default(self):
        # Sending precision rounds sub-cent coins to zero, so it must not be sent
        # unless the caller explicitly asks for it.
        fetch_market_chart('bitcoin', client=self.client)
        self.assertNotIn('precision', self.client.chart_calls[0])

    def test_precision_forwarded_when_given(self):
        fetch_market_chart('bitcoin', precision=2, client=self.client)
        self.assertEqual(self.client.chart_calls[0]['precision'], 2)

    def test_precision_zero_is_forwarded(self):
        # 0 is falsy but a legitimate precision, so it must not be dropped.
        fetch_market_chart('bitcoin', precision=0, client=self.client)
        self.assertEqual(self.client.chart_calls[0]['precision'], 0)

    def test_rejects_none_id(self):
        with self.assertRaises(ValueError):
            fetch_market_chart(None, client=self.client)

    def test_rejects_empty_id(self):
        with self.assertRaises(ValueError):
            fetch_market_chart('', client=self.client)

    def test_rejects_whitespace_only_id(self):
        with self.assertRaises(ValueError):
            fetch_market_chart('   ', client=self.client)

    def test_rejects_non_string_id(self):
        with self.assertRaises(ValueError):
            fetch_market_chart(123, client=self.client)

    def test_rejects_id_before_calling_api(self):
        # Validation should short-circuit rather than burn a rate-limited request.
        with self.assertRaises(ValueError):
            fetch_market_chart(None, client=self.client)
        self.assertEqual(self.client.chart_calls, [])

    def test_raises_on_empty_response(self):
        client = FakeCoinGeckoClient(charts={'ghost': {}})
        with self.assertRaises(ValueError):
            fetch_market_chart('ghost', client=client)

    def test_raises_on_response_without_prices_key(self):
        client = FakeCoinGeckoClient(charts={'ghost': {'market_caps': []}})
        with self.assertRaises(ValueError):
            fetch_market_chart('ghost', client=client)

    def test_raises_on_empty_price_list(self):
        client = FakeCoinGeckoClient(charts={'ghost': {'prices': []}})
        with self.assertRaises(ValueError):
            fetch_market_chart('ghost', client=client)

    def test_api_errors_propagate(self):
        client = FakeCoinGeckoClient(charts={'bitcoin': RuntimeError('429 rate limited')})
        with self.assertRaises(RuntimeError):
            fetch_market_chart('bitcoin', client=client)


class TestCredentials(unittest.TestCase):
    """
    Keys are read from the environment, never from a file in the working tree.

    Demo and Pro keys are not interchangeable: they select different base URLs
    and different request headers, so sending one as the other silently targets
    the wrong endpoint.
    """

    def test_no_key_uses_the_public_endpoint(self):
        with with_env():
            client = get_client()
        self.assertIsNone(client.extra_params)
        self.assertNotIn('pro-api', client.api_base_url)

    def test_demo_key_from_environment(self):
        with with_env(**{DEMO_API_KEY_ENV: 'CG-demo'}):
            client = get_client()
        self.assertEqual(client.extra_params, {'x_cg_demo_api_key': 'CG-demo'})

    def test_demo_key_keeps_the_public_base_url(self):
        with with_env(**{DEMO_API_KEY_ENV: 'CG-demo'}):
            client = get_client()
        self.assertNotIn('pro-api', client.api_base_url)

    def test_pro_key_from_environment(self):
        with with_env(**{API_KEY_ENV: 'CG-pro'}):
            client = get_client()
        self.assertEqual(client.extra_params, {'x_cg_pro_api_key': 'CG-pro'})

    def test_pro_key_switches_to_the_pro_base_url(self):
        with with_env(**{API_KEY_ENV: 'CG-pro'}):
            client = get_client()
        self.assertIn('pro-api', client.api_base_url)

    def test_pro_key_wins_when_both_are_set(self):
        with with_env(**{API_KEY_ENV: 'CG-pro', DEMO_API_KEY_ENV: 'CG-demo'}):
            client = get_client()
        self.assertEqual(client.extra_params, {'x_cg_pro_api_key': 'CG-pro'})

    def test_surrounding_whitespace_is_stripped(self):
        # A key pasted into a shell profile often carries a trailing newline.
        with with_env(**{DEMO_API_KEY_ENV: '  CG-demo\n'}):
            client = get_client()
        self.assertEqual(client.extra_params, {'x_cg_demo_api_key': 'CG-demo'})

    def test_blank_variable_counts_as_unset(self):
        # An empty export must not flip the client to the paid endpoint.
        with with_env(**{API_KEY_ENV: '   '}):
            client = get_client()
        self.assertIsNone(client.extra_params)
        self.assertNotIn('pro-api', client.api_base_url)

    def test_explicit_argument_overrides_environment(self):
        with with_env(**{DEMO_API_KEY_ENV: 'CG-from-env'}):
            client = get_client(demo_api_key='CG-explicit')
        self.assertEqual(client.extra_params, {'x_cg_demo_api_key': 'CG-explicit'})

    def test_empty_argument_ignores_environment(self):
        with with_env(**{DEMO_API_KEY_ENV: 'CG-from-env'}):
            client = get_client(demo_api_key='')
        self.assertIsNone(client.extra_params)


class TestDescribeCredentials(unittest.TestCase):
    """The credential summary must never leak the key itself."""

    def test_reports_missing_credentials(self):
        with with_env():
            message = describe_credentials()
        self.assertIn('No API key configured', message)
        self.assertIn(DEMO_API_KEY_ENV, message)

    def test_reports_demo_key(self):
        with with_env(**{DEMO_API_KEY_ENV: 'CG-demo'}):
            self.assertIn('Demo key', describe_credentials())

    def test_reports_pro_key(self):
        with with_env(**{API_KEY_ENV: 'CG-pro'}):
            self.assertIn('Pro key', describe_credentials())

    def test_never_reveals_the_key(self):
        secret = 'CG-supersecretvalue'
        with with_env(**{API_KEY_ENV: secret, DEMO_API_KEY_ENV: secret}):
            message = describe_credentials()
        self.assertNotIn(secret, message)
        self.assertNotIn('supersecret', message)


class TestFetchTopCoins(unittest.TestCase):
    """Standard and edge cases for fetch_top_coins."""

    def test_extracts_ids_in_order(self):
        client = FakeCoinGeckoClient(markets=[{'id': 'bitcoin'}, {'id': 'ethereum'}])
        self.assertEqual(fetch_top_coins(limit=2, client=client), ['bitcoin', 'ethereum'])

    def test_forwards_limit_as_per_page(self):
        client = FakeCoinGeckoClient(markets=[])
        fetch_top_coins(limit=7, client=client)

        call = client.market_calls[0]
        self.assertEqual(call['per_page'], 7)
        self.assertEqual(call['order'], 'market_cap_desc')
        self.assertEqual(call['page'], 1)
        self.assertFalse(call['sparkline'])

    def test_forwards_vs_currency(self):
        client = FakeCoinGeckoClient(markets=[])
        fetch_top_coins(vs_currency='eur', client=client)
        self.assertEqual(client.market_calls[0]['vs_currency'], 'eur')

    def test_skips_records_without_id(self):
        client = FakeCoinGeckoClient(markets=[{'id': 'bitcoin'}, {'symbol': 'eth'}, {'id': None}])
        self.assertEqual(fetch_top_coins(client=client), ['bitcoin'])

    def test_skips_records_with_empty_id(self):
        client = FakeCoinGeckoClient(markets=[{'id': ''}, {'id': 'bitcoin'}])
        self.assertEqual(fetch_top_coins(client=client), ['bitcoin'])

    def test_returns_empty_list_on_api_error(self):
        # Top-coin lookup is best-effort: a failure must not crash the caller.
        client = FakeCoinGeckoClient(markets=RuntimeError('boom'))
        self.assertEqual(fetch_top_coins(client=client), [])

    def test_returns_empty_list_for_empty_response(self):
        self.assertEqual(fetch_top_coins(client=FakeCoinGeckoClient(markets=[])), [])


if __name__ == '__main__':
    unittest.main()
