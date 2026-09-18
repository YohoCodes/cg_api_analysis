"""
Tests for chart_analysis.plotting.

A non-interactive backend is selected before pyplot is imported so the suite
never opens a window.
"""

import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ..plotting import plot_price, plot_prices
from .helpers import make_table, make_tables


class PlottingTestCase(unittest.TestCase):
    """Closes any figure a test leaves behind."""

    def setUp(self):
        self.addCleanup(plt.close, 'all')


class TestPlotPrice(PlottingTestCase):
    """Single-coin chart."""

    def setUp(self):
        super().setUp()
        self.df = make_table([100.0, 110.0, 120.0])

    def test_returns_axes(self):
        ax = plot_price(self.df, 'bitcoin')
        self.assertIsInstance(ax, plt.Axes)

    def test_creates_a_figure_when_no_axes_given(self):
        plot_price(self.df, 'bitcoin')
        self.assertEqual(len(plt.get_fignums()), 1)

    def test_draws_onto_supplied_axes(self):
        fig, ax = plt.subplots()
        returned = plot_price(self.df, 'bitcoin', ax=ax)

        self.assertIs(returned, ax)
        self.assertEqual(len(plt.get_fignums()), 1)

    def test_title_names_the_coin(self):
        ax = plot_price(self.df, 'bitcoin')
        self.assertIn('Bitcoin', ax.get_title())

    def test_axis_labels(self):
        ax = plot_price(self.df, 'bitcoin', vs_currency='eur')
        self.assertEqual(ax.get_xlabel(), 'Date')
        self.assertIn('EUR', ax.get_ylabel())

    def test_plots_every_close_price(self):
        ax = plot_price(self.df, 'bitcoin')
        line = ax.get_lines()[0]
        self.assertEqual(list(line.get_ydata()), self.df['daily_close'].tolist())

    def test_hyphenated_coin_id_is_titled(self):
        ax = plot_price(self.df, 'shiba-inu')
        self.assertIn('Shiba-inu', ax.get_title())


class TestPlotPrices(PlottingTestCase):
    """Multi-coin chart."""

    def setUp(self):
        super().setUp()
        self.tables = make_tables({
            'bitcoin': [100.0, 110.0, 120.0],
            'ethereum': [50.0, 55.0, 60.0],
        })

    def test_one_subplot_per_coin(self):
        fig = plot_prices(self.tables, show=False)
        self.assertEqual(len(fig.axes), 2)

    def test_single_coin_still_works(self):
        # A lone coin gives a bare Axes rather than an array, which the code
        # has to wrap before iterating.
        fig = plot_prices(make_tables({'bitcoin': [1.0, 2.0, 3.0]}), show=False)
        self.assertEqual(len(fig.axes), 1)

    def test_subplot_order_follows_coin_ids(self):
        fig = plot_prices(self.tables, coin_ids=['ethereum', 'bitcoin'], show=False)
        titles = [ax.get_title() for ax in fig.axes]
        self.assertIn('Ethereum', titles[0])
        self.assertIn('Bitcoin', titles[1])

    def test_subset_plots_only_requested_coins(self):
        fig = plot_prices(self.tables, coin_ids=['bitcoin'], show=False)
        self.assertEqual(len(fig.axes), 1)

    def test_currency_reaches_every_subplot(self):
        fig = plot_prices(self.tables, vs_currency='gbp', show=False)
        for ax in fig.axes:
            self.assertIn('GBP', ax.get_ylabel())

    def test_show_false_does_not_display(self):
        calls = []
        original = plt.show
        plt.show = lambda *a, **k: calls.append(1)
        self.addCleanup(setattr, plt, 'show', original)

        plot_prices(self.tables, show=False)
        self.assertEqual(calls, [])

    def test_show_true_displays_once(self):
        calls = []
        original = plt.show
        plt.show = lambda *a, **k: calls.append(1)
        self.addCleanup(setattr, plt, 'show', original)

        plot_prices(self.tables, show=True)
        self.assertEqual(len(calls), 1)

    def test_empty_tables_raises(self):
        with self.assertRaises(ValueError):
            plot_prices({}, show=False)

    def test_empty_tables_error_names_the_problem(self):
        # Without this guard matplotlib reports "Number of rows must be a positive
        # integer", which says nothing about the missing coins.
        with self.assertRaises(ValueError) as caught:
            plot_prices({}, show=False)

        message = str(caught.exception)
        self.assertIn('No coins to plot', message)
        self.assertIn('get_market_tables', message)

    def test_empty_coin_ids_raises(self):
        with self.assertRaises(ValueError):
            plot_prices(self.tables, coin_ids=[], show=False)

    def test_unknown_coin_raises_with_available_names(self):
        with self.assertRaises(ValueError) as caught:
            plot_prices(self.tables, coin_ids=['dogecoin'], show=False)

        message = str(caught.exception)
        self.assertIn('dogecoin', message)
        self.assertIn('bitcoin', message)

    def test_no_figure_left_open_after_a_rejected_call(self):
        with self.assertRaises(ValueError):
            plot_prices({}, show=False)
        self.assertEqual(plt.get_fignums(), [])


if __name__ == '__main__':
    unittest.main()
