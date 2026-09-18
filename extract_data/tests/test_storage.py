"""Tests for extract_data.storage: cache paths and CSV round-tripping."""

import os
import tempfile
import unittest

import pandas as pd

from ..storage import dataset_path, has_table, load_table, save_table


def sample_table():
    """Builds a small market chart table shaped like reformat_data's output."""
    # Built without a freq, matching reformat_data's index (a freq would not
    # survive the CSV round trip anyway).
    index = pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03'], name='date')
    return pd.DataFrame(
        {'daily_close': [100.0, 110.0, 99.0], 'percent_change': [1.0, 10.0, -10.0]},
        index=index
    )


class TestDatasetPath(unittest.TestCase):
    """Cache file naming."""

    def test_builds_expected_name(self):
        self.assertEqual(
            dataset_path('bitcoin', 'usd', 364),
            os.path.join('datasets', 'bitcoin_usd_364days.csv')
        )

    def test_honors_custom_directory(self):
        self.assertEqual(
            dataset_path('bitcoin', 'usd', 364, datasets_dir='/tmp/cache'),
            os.path.join('/tmp/cache', 'bitcoin_usd_364days.csv')
        )

    def test_currency_and_days_are_part_of_the_name(self):
        # Otherwise a eur/30-day pull would overwrite the usd/364-day cache.
        usd = dataset_path('bitcoin', 'usd', 364)
        eur = dataset_path('bitcoin', 'eur', 364)
        short = dataset_path('bitcoin', 'usd', 30)
        self.assertEqual(len({usd, eur, short}), 3)

    def test_hyphenated_coin_ids_are_preserved(self):
        self.assertIn('shiba-inu_usd_364days.csv', dataset_path('shiba-inu', 'usd', 364))


class TestSaveAndLoadTable(unittest.TestCase):
    """Writing tables to disk and reading them back."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'bitcoin_usd_364days.csv')

    def test_round_trip_preserves_values(self):
        original = sample_table()
        save_table(original, self.path)
        pd.testing.assert_frame_equal(load_table(self.path), original)

    def test_round_trip_preserves_datetime_index(self):
        save_table(sample_table(), self.path)
        loaded = load_table(self.path)
        self.assertEqual(loaded.index.name, 'date')
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(loaded.index))

    def test_creates_missing_directories(self):
        nested = os.path.join(self.tmp.name, 'deep', 'deeper', 'table.csv')
        save_table(sample_table(), nested)
        self.assertTrue(os.path.exists(nested))

    def test_bare_filename_needs_no_directory(self):
        # dirname('table.csv') is '', which must not reach makedirs.
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, cwd)

        save_table(sample_table(), 'table.csv')
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, 'table.csv')))

    def test_overwrites_existing_file(self):
        save_table(sample_table(), self.path)
        replacement = sample_table().head(1)
        save_table(replacement, self.path)
        self.assertEqual(len(load_table(self.path)), 1)

    def test_empty_table_round_trips(self):
        empty = sample_table().iloc[0:0]
        save_table(empty, self.path)
        self.assertTrue(load_table(self.path).empty)


class TestHasTable(unittest.TestCase):
    """Cache presence checks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_false_when_missing(self):
        self.assertFalse(has_table(os.path.join(self.tmp.name, 'nope.csv')))

    def test_true_after_save(self):
        path = os.path.join(self.tmp.name, 'yes.csv')
        save_table(sample_table(), path)
        self.assertTrue(has_table(path))


if __name__ == '__main__':
    unittest.main()
