from cg_api_analysis import analyze_coin_market_chart


coin_analysis = analyze_coin_market_chart(limit = 5)
print(coin_analysis.correlation_analysis())