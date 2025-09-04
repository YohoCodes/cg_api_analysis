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

## Example Scripts

### Example 1: Top 5 Coins Analysis (`analysis_ex1.py`)

This script demonstrates basic usage with automatic top coin selection:

```bash
python analysis_ex1.py
```

**What it does:**
- Retrieves the top 5 cryptocurrencies by market cap
- Performs both price correlation and return correlation analysis
- Prints results in a readable format

### Example 2: Custom Coin List Analysis (`analysis_ex2.py`)

This script shows how to analyze a custom list of cryptocurrencies:

```bash
python analysis_ex2.py
```

**What it does:**
- Uses a predefined list of top 50 cryptocurrencies
- Limits analysis to the first 8 coins to avoid API rate limits
- Demonstrates manual coin selection vs automatic selection

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

## Data Structure

The analysis returns correlation data in the following format:

```
   coin1      coin2  correlation
0  bitcoin  ethereum     0.8234
1  bitcoin    solana     0.7123
2  ethereum   solana     0.6543
```

## Project Structure

```
cg_api_analysis/
├── chart_analysis/
│   └── cg_api_analysis.py    # Main analysis class
├── utils/
│   └── search.py             # Utility functions
├── datasets/                 # Cached data files
├── analysis_ex1.py          # Basic usage example
├── analysis_ex2.py          # Custom coin list example
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

## Dependencies

Key dependencies include:
- `pandas`: Data manipulation and analysis
- `matplotlib`: Chart plotting
- `pycoingecko`: CoinGecko API client
- `requests`: HTTP requests
- `numpy`: Numerical computations

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

[Add your license information here]

## Support

For issues and questions, please open an issue on the repository.
