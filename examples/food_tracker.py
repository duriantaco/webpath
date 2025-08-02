import asyncio
import logging
from webpath.core import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RealWorldDemo")

def smart_retry_logic(response):
    if response.status_code >= 500:
        wait_time = 3.0
        print(f" Server error {response.status_code}, retrying in {wait_time}s...")
        return wait_time
    elif response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "5")
        wait_time = float(retry_after)
        print(f" Rate limited, refreshing in {wait_time}s...")
        return wait_time
    return None

async def demo_food_database():
    
    async with Client(
        "https://world.openfoodfacts.org/api/v2",
        headers={
            "User-Agent": "WebPath-Demo/1.0 (educational-demo)",
            "Accept": "application/json"
        },
        cache_ttl=300, 
        retries=smart_retry_logic,
        rate_limit=0.5,
        enable_logging=True
    ) as food_api:
        
        try:
            print(" Searching for chocolate products...")
            search_response = await food_api.aget(
                "search", 
                search_terms="chocolate",
                page_size=5,
                fields="product_name,brands,nutrition_grades,energy_100g,countries_tags"
            )
            
            products = search_response.find_all("products[*].{name: product_name, brand: brands, grade: nutrition_grades, energy: energy_100g, countries: countries_tags[0]}")
            
            print(f" Found {len(products)} chocolate products:")
            for i, product in enumerate(products, 1):
                name = product.get('name', 'Unknown')[:50]
                brand = product.get('brand', 'No brand')[:30]
                grade = product.get('grade', 'Not rated')
                energy = product.get('energy', 'Unknown')
                country = product.get('countries', 'Unknown').replace('en:', '')
                
                print(f"  {i}. {name}")
                print(f"     Brand: {brand} | Grade: {grade} | Energy: {energy} kcal/100g | From: {country}")
            
            print(f"\n Getting info for Coca-Cola...")
            coke_response = await food_api.aget("product", "5449000000996") 
            
            if coke_response.status_code == 200:
                product_info = coke_response.extract(
                    "product.product_name",
                    "product.brands", 
                    "product.nutriments.energy_100g",
                    "product.nutriments.sugars_100g",
                    "product.ingredients_text_en",
                    "product.countries_tags[0]"
                )
                
                name, brands, energy, sugars, ingredients, country = product_info
                
                print(f"* Product: {name}")
                print(f"* Brands: {brands}")
                print(f"* Energy: {energy} kcal/100g")
                print(f"* Sugars: {sugars}g/100g")
                print(f"* Country: {country}")

                if ingredients:
                    print(f"Ingredients: {ingredients[:100]}...")
                else:
                    print("Ingredients: Not available")
                
                print(f"\nResponse inspection:")
                print(f"Status: {coke_response.status_code}")
                print(f"Content-Type: {coke_response.headers.get('content-type')}")
                
            else:
                print("Could not find Coca-Cola product")
                
        except Exception as e:
            logger.error(f"Food API error: {e}")

if __name__ == "__main__":
    asyncio.run(demo_food_database())
    
    try:
        with open('food_tracker.log', 'r') as f:
            print(f.read())
    except FileNotFoundError:
        print("No log file found. Ensure logging is configured correctly.")