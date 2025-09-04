from chart_analysis import analyze_coin_market_chart

# Instead of using limit = 5, we use the top 50 coins by market cap.
# This shows the flexibility of the analyze_coin_market_chart class.
# Rather than calling the API, we can manually specify the coins we want to analyze.
# I've chosen the top 50 coins by market cap, excluding wrapped and stable coins.
top_50_coins = [
    "bitcoin",
    "ethereum",
    "binancecoin",
    "solana",
    "ripple",
    "dogecoin",
    "toncoin",
    "cardano",
    "shiba-inu",
    "avalanche-2",
    "bitcoin-cash",
    "polkadot",
    "tron",
    "chainlink",
    "polygon",
    "litecoin",
    "internet-computer",
    "uniswap",
    "leo-token",
    "ethereum-classic",
    "cosmos",
    "filecoin",
    "aptos",
    "lido-dao",
    "crypto-com-chain",
    "mantle",
    "render-token",
    "near",
    "monero",
    "hedera-hashgraph",
    "arbitrum",
    "the-graph",
    "quant-network",
    "vechain",
    "maker",
    "kaspa",
    "algorand",
    "optimism",
    "stellar",
    "bsv",                 # Bitcoin SV
    "decentraland",
    "flow",
    "tezos",
    "apecoin",
    "eos",
    "immutable-x",
    "multiversx",          # EGLD (formerly Elrond)
    "axie-infinity",
    "thorchain",
]

# Limiting the number of coins to 8 to avoid rate limit error
coin_analysis = analyze_coin_market_chart(id=top_50_coins[:8])

print(coin_analysis.price_correlation())
print('\n')
print(coin_analysis.return_correlation())