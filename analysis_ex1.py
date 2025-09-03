from chart_analysis import analyze_coin_market_chart

# This example demonstrates the basic usage of the analyze_coin_market_chart class.
# We use limit = 5 to analyze the top 5 cryptocurrencies by market cap.
# This is useful for quick analysis of the most popular coins.
coin_analysis = analyze_coin_market_chart(limit = 5)

print(coin_analysis.price_correlation())
print('\n')
print(coin_analysis.return_correlation())