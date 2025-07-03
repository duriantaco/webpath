from webpath import WebPath

def check_crypto_prices_with_shortcuts():
    print("Testing JSON Shortcuts with Real CoinGecko API\n")
    
    api = WebPath("https://api.coingecko.com/api/v3").with_logging()
    
    prices = api / "simple" / "price"
    response = prices.with_query(
        ids="bitcoin,ethereum,cardano",
        vs_currencies="usd",
        include_24hr_change="true"
    ).get()

    print("Using .find() method:")
    coins = ["bitcoin", "ethereum", "cardano"]
    for coin in coins:
        price = response.find(f"{coin}.usd")
        change = response.find(f"{coin}.usd_24h_change")
        direction = "UP" if change > 0 else "DOWN"
        print(f"{coin}: ${price:,.2f} {direction} {change:.1f}%")
    
    print("\nUsing .find_all() with wildcards:")
    all_prices = response.find_all("*.usd")
    all_changes = response.find_all("*.usd_24h_change")
    coin_names = list(response.json_data.keys())
    
    for i, coin in enumerate(coin_names):
        price = all_prices[i]
        change = all_changes[i]
        direction = "UP" if change > 0 else "DOWN"
        print(f"   {coin}: ${price:,.2f} {direction} {change:.1f}%")
    
    print("\nUsing .extract() for specific coins:")
    btc_price, btc_change = response.extract("bitcoin.usd", "bitcoin.usd_24h_change")
    eth_price, eth_change = response.extract("ethereum.usd", "ethereum.usd_24h_change")
    
    print(f" Bitcoin: ${btc_price:,.2f} ({'UP' if btc_change > 0 else 'DOWN'} {btc_change:.1f}%)")
    print(f" Ethereum: ${eth_price:,.2f} ({'UP' if eth_change > 0 else 'DOWN'} {eth_change:.1f}%)")
    
    print("\nUsing .search() to find all USD data:")
    usd_values = response.search("usd")
    print(f" Found {len(usd_values)} USD values")
    
    print("\nUsing .has_path() to check data availability:")
    print(f" Has Bitcoin data? {response.has_path('bitcoin')}")
    print(f" Has Bitcoin USD price? {response.has_path('bitcoin.usd')}")
    print(f" Has volume data? {response.has_path('bitcoin.usd_24h_vol')}")
    print(f"Has Dogecoin data? {response.has_path('dogecoin')}")
    
    print("\nUsing defaults for missing data:")
    doge_price = response.find("dogecoin.usd", default="Not requested")
    btc_volume = response.find("bitcoin.usd_24h_vol", default="Not available")
    print(f" Dogecoin price: {doge_price}")
    print(f" Bitcoin volume: {btc_volume}")

def test_complex_api():
    print("\nTesting with detailed Bitcoin data:")
    
    try:
        api = WebPath("https://api.coingecko.com/api/v3").with_logging()
        response = (api / "coins" / "bitcoin").get()
        
        name = response.find("name")
        symbol = response.find("symbol")
        current_price = response.find("market_data.current_price.usd")
        market_cap = response.find("market_data.market_cap.usd")
        total_supply = response.find("market_data.total_supply")
        
        print(f" Coin: {name} ({symbol.upper()})")
        print(f" Price: ${current_price:,.2f}")
        print(f" Market Cap: ${market_cap:,.0f}")
        print(f" Total Supply: {total_supply:,.0f}")
        
        all_prices = response.find_all("market_data.current_price.*")
        print(f" Found prices in {len(all_prices)} currencies")
        
        eur_price = response.find("market_data.current_price.eur")
        gbp_price = response.find("market_data.current_price.gbp")
        
        if eur_price: print(f" EUR: €{eur_price:,.2f}")
        if gbp_price: print(f" GBP: £{gbp_price:,.2f}")
        
    except Exception as e:
        print(f"API test failed: {e}")

if __name__ == "__main__":
    check_crypto_prices_with_shortcuts()
    test_complex_api()