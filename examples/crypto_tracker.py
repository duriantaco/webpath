import logging
import httpx
import asyncio
from webpath.core import Client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='crypto_tracker.log',
    filemode='w'
)
logger = logging.getLogger("CryptoTrackerApp")
print("Logging configured. API requests will be saved to 'crypto_tracker.log'.")

async def track_crypto_prices():

    coingecko_api = Client(
        "https://api.coingecko.com/api/v3",
        enable_logging=True, 
        retries=2,
        cache_ttl=60
    )

    coins_to_track = ["bitcoin", "ethereum", "solana"]
    
    print("\n--- Getting crypto prices... ---")
    try:
        response = coingecko_api.get(
            "simple", "price", 
            ids=",".join(coins_to_track), 
            vs_currencies="usd"
        )

        print("Current Prices:")
        for coin in coins_to_track:
            price = response.find(f"{coin}.usd", default="N/A")
            print(f" - {coin.capitalize():<10}: ${price:,.2f}")

        ## async here
        print("\n Getting trending coins")
        trending_resp = await coingecko_api.aget("search", "trending")
        
        trending_coins = trending_resp.extract("coins[*].item.name", flatten=True)
        
        if trending_coins:
            print(" Top 3 Trending Coins:")
            for coin_name in trending_coins[:3]:
                print(f"  - {coin_name}")

    except httpx.RequestError as e:
        logger.error(f"Could not connect to CoinGecko API: {e}")
        print(f"Could not connect to API. See 'crypto_tracker.log' for details")
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP Error {e.response.status_code}: {e}")
        print(f"HTTP Error {e.response.status_code}: {e}")
        
    finally:
        coingecko_api.close()
        await coingecko_api.aclose()

if __name__ == "__main__":
    asyncio.run(track_crypto_prices())
    
    print("\n--- Reviewing the 'crypto_tracker.log' File ---")
    try:
        with open('crypto_tracker.log', 'r') as f:
            print(f.read())
    except FileNotFoundError:
        print("Log file not created.")