# Crypto API Analysis

A Python toolkit for analyzing cryptocurrency market data using the CoinGecko API. This project provides tools for retrieving, processing, and analyzing historical market chart data for cryptocurrencies with correlation analysis capabilities.

## Features

- **Multi-coin Analysis**: Analyze single coins or multiple cryptocurrencies simultaneously
- **Automatic Top Coins**: Retrieve top cryptocurrencies by market cap automatically
- **Correlation Analysis**: Analyze both price correlations and return correlations between coin pairs
- **Data Caching**: Automatically cache data to avoid repeated API calls
- **Flexible Data Retrieval**: Support for custom coin lists or automatic top coin selection

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cg_api_analysis
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

API keys are read from environment variables. Nothing secret is ever stored in the
working tree.

| Variable | Tier | Notes |
| --- | --- | --- |
| `COINGECKO_DEMO_API_KEY` | Free Demo account | Public endpoint, higher rate limit than anonymous |
| `COINGECKO_API_KEY` | Paid Pro plan | Switches to the Pro endpoint; rejects Demo keys |

Set one in your shell:

```bash
export COINGECKO_DEMO_API_KEY='CG-your-key-here'
```

To persist it, add that line to `~/.zshrc`, or copy `.env.example` to `.env` (gitignored),
fill in the key, and load it per session:

```bash
set -a; source .env; set +a
```

Neither variable is required — without one the client uses the anonymous public endpoint,
which has the strictest rate limits. To check what is configured, without printing the key:

```python
import extract_data
print(extract_data.describe_credentials())
# Demo key found in $COINGECKO_DEMO_API_KEY.
```

Keys are picked up automatically by `analyze_coin_market_chart` and by every
`extract_data` function that creates its own client.

## Quick Start

### Basic Usage

```python
from chart_analysis import analyze_coin_market_chart

# Analyze top 5 cryptocurrencies by market cap
coin_analysis = analyze_coin_market_chart(limit=5)

# Get price correlations
price_corr = coin_analysis.price_correlation()
print(price_corr)

# Get return correlations
return_corr = coin_analysis.return_correlation()
print(return_corr)
```

### Manual Coin Selection

```python
# Analyze specific cryptocurrencies
coins = ["bitcoin", "ethereum", "solana"]
coin_analysis = analyze_coin_market_chart(id=coins)

# Perform correlation analysis
correlations = coin_analysis.return_correlation()
```

### Using the Packages Directly

`analyze_coin_market_chart` is a convenience wrapper. The two packages can also be used on
their own — useful when you already have data, or want to analyze something other than a
CoinGecko chart:

```python
import extract_data
import chart_analysis

# Retrieval only: loads cached CSVs from datasets/, calls the API for anything missing
tables, failed = extract_data.get_market_tables(["bitcoin", "ethereum", "solana"])

# Analysis only: operates on {coin_id: DataFrame}, no API involved
print(chart_analysis.return_correlation(tables))
chart_analysis.plot_prices(tables)
```

## Example Scripts

### Example 1: Custom Coin List Analysis (`analysis_ex1.py`)

This script shows how to analyze a custom list of cryptocurrencies:

```bash
python analysis_ex1.py
```

**What it does:**
- Uses a predefined list of top 50 cryptocurrencies
- Limits analysis to the first 8 coins to avoid API rate limits
- Demonstrates manual coin selection vs automatic selection

### Example 2: Top Coins Analysis (`analysis_ex2.py`)

This script demonstrates basic usage with automatic top coin selection:

```bash
python analysis_ex2.py
```

**What it does:**
- Retrieves the top cryptocurrencies by market cap
- Performs both price correlation and return correlation analysis
- Prints results in a readable format

## API Reference

### Main Class: `analyze_coin_market_chart`

#### Constructor Parameters

- `id` (str or list): CoinGecko coin ID(s) (default: 'bitcoin')
- `vs_currency` (str): Target currency (default: 'usd')
- `days` (int): Number of days of data (default: 364)
- `limit` (int or bool): If integer, automatically get top N coins by market cap

#### Key Methods

- `price_correlation()`: Analyze correlation of daily close prices between coin pairs
- `return_correlation()`: Analyze correlation of daily returns between coin pairs
- `plot()`: Generate price charts for analyzed coins
- `save_tables(coin_list)`: Cache data for multiple coins
- `reformat_data(chart_data)`: Convert raw API data to pandas DataFrame

### Package: `extract_data`

Everything that touches the CoinGecko API or the `datasets/` cache.

- `fetch_market_chart(coin_id, ...)`: Raw market chart payload for one coin
- `fetch_top_coins(limit, ...)`: Top coin IDs by market cap
- `reformat_data(chart_data)`: Raw API payload to a date-indexed DataFrame
- `get_market_chart_table(coin_id, ...)`: Fetch and reformat one coin in a single call
- `get_market_tables(coin_ids, ...)`: Cache-aware tables for many coins; returns `(tables, failed)`
- `TopCoinsCache`: Top-coin lookups cached for the day
- `dataset_path(...)` / `load_table(path)` / `save_table(df, path)` / `has_table(path)`: CSV cache helpers

### Package: `chart_analysis`

Analysis over `{coin_id: DataFrame}` mappings — no network access.

- `price_correlation(tables, coin_ids=None)`: Correlation of daily close prices between coin pairs
- `return_correlation(tables, coin_ids=None)`: Correlation of daily returns between coin pairs

Both return `None` — and print the reason — when no ranking can be produced: fewer than two
coins, fewer than two shared dates, or no pair with a defined correlation. Pairs that are
individually undefined are dropped from the ranking and reported, so a short result always
comes with an explanation:

```
Note: 5 of 6 coin pairs have an undefined correlation and were left out of the ranking.
  Constant over this window (zero variance): tether, usd-coin
    A value that never moves has no correlation with anything - this is
    normal for stablecoins pegged to a currency. To fix: drop these coins
    from the analysis, or use a window long enough for the peg to move.
```

- `plot_prices(tables, ...)`: One price subplot per coin
- `plot_price(df, coin_id, ...)`: A single coin's price chart, optionally onto your own axes
- `analyze_coin_market_chart`: The wrapper class documented above

## Data Structure

The analysis returns correlation data in the following format:

```
   coin1      coin2  correlation
0  bitcoin  ethereum     0.8234
1  bitcoin    solana     0.7123
2  ethereum   solana     0.6543
```

## Project Structure

The project is split into two local packages: `extract_data` fetches and caches data,
`chart_analysis` analyzes it. Neither depends on the other's internals — `chart_analysis`
simply consumes the DataFrames `extract_data` returns.

```
cg_api_analysis/
├── extract_data/             # Data retrieval (CoinGecko API + disk cache)
│   ├── client.py             # Raw API calls
│   ├── transform.py          # Raw API payload -> pandas DataFrame
│   ├── storage.py            # CSV cache paths, load/save
│   └── market_data.py        # Cache-aware retrieval, top-coin caching
├── chart_analysis/           # Analysis over the retrieved DataFrames
│   ├── correlation.py        # Pairwise price / return correlation
│   ├── plotting.py           # Price charts
│   └── market_chart.py       # analyze_coin_market_chart (wires both packages)
├── utils/
│   └── search.py             # Utility functions
├── datasets/                 # Cached data files
├── analysis_ex1.py          # Custom coin list example
├── analysis_ex2.py          # Basic usage example
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

## Testing

Tests live inside each package (`extract_data/tests/`, `chart_analysis/tests/`) and use the
standard library's `unittest` — no extra dependencies to install.

```bash
python -m unittest discover -s . -p "test_*.py"     # everything
python -m unittest discover -s extract_data/tests -t .   # retrieval only
python -m unittest discover -s chart_analysis/tests -t . # analysis only
```

Every test injects a fake CoinGecko client and a temporary cache directory, so the suite
makes no network calls, never consumes API rate limit, and never reads or writes `datasets/`.

## Dependencies

Key dependencies include:
- `pandas`: Data manipulation and analysis
- `matplotlib`: Chart plotting
- `pycoingecko`: CoinGecko API client
- `requests`: HTTP requests
- `numpy`: Numerical computations

## Data Sources

This project uses the [CoinGecko API](https://www.coingecko.com/en/api) to retrieve cryptocurrency market data. CoinGecko provides comprehensive cryptocurrency data including historical prices, market cap, volume, and more.

### Attribution
- **Data Source**: [CoinGecko](https://www.coingecko.com/)
- **API Documentation**: [CoinGecko API Docs](https://www.coingecko.com/en/api/documentation)
- **Terms of Service**: [CoinGecko API Terms](https://www.coingecko.com/en/api_terms)

Please ensure compliance with CoinGecko's API terms of service when using this project.

## Rate Limiting

The CoinGecko API has rate limits for free users. The project includes:
- Automatic data caching to minimize API calls
- Built-in rate limit handling
- Recommendations for analysis batch sizes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please open an issue on the repository.
