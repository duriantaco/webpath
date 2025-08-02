import asyncio
import logging
from webpath.core import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FinalDemo")

def retry_with_backoff(response):
    if response.status_code >= 500:
        wait_time = 2.0
        print(f"Server error {response.status_code}, retrying in {wait_time}s...")
        return wait_time
    elif response.status_code == 429:
        wait_time = 3.0
        print(f"Rate limited, waiting {wait_time}s...")
        return wait_time
    return None

async def demo_university_search():

    async with Client(
        "http://universities.hipolabs.com",
        cache_ttl=300, 
        retries=retry_with_backoff,
        enable_logging=True,
        timeout=15
    ) as uni_api:
        
        try:
            countries = ["United States", "United Kingdom", "Canada", "Australia"]
            
            for country in countries:
                print(f"\n Searching universities in {country}...")
                
                response = await uni_api.aget(
                    "search",
                    country=country
                )
                
                universities = response.find_all(
                    "[?domains[0]].{name: name, domain: domains[0], website: web_pages[0], state: state_province}"
                )
                
                if country == "United States":
                    edu_unis = [u for u in universities if u.get('domain', '').endswith('.edu')]
                    universities = edu_unis[:8]
                else:
                    universities = universities[:8]
                
                print(f"Found {len(universities)} universities:")
                
                for i, uni in enumerate(universities, 1):
                    name = uni.get('name', 'Unknown')[:50]
                    domain = uni.get('domain', 'No domain')
                    state = uni.get('state', 'N/A')
                    website = uni.get('website', 'No website')
                    
                    print(f" {i}. {name}")
                    print(f" Domain: {domain} | State: {state}")
                    print(f" Website: {website}")
                
                await asyncio.sleep(1)
            
            print(f"\n Searching for tech focused college...")
            
            tech_response = await uni_api.aget("search", name="technology")
            
            tech_unis = tech_response.find_all(
                "[*].{name: name, country: country, domain: domains[0]}"
            )
            
            by_country = {}
            for uni in tech_unis:
                country = uni.get('country', 'Unknown')
                if country not in by_country:
                    by_country[country] = []
                by_country[country].append(uni)
            
            print(f"Technology universities by country:")
            for country, unis in list(by_country.items())[:5]:
                print(f" {country}: {len(unis)} universities")
                for uni in unis[:2]: 
                    print(f" - {uni.get('name', 'Unknown')}")
                    
        except Exception as e:
            logger.error(f"University API error: {e}")

async def main():
    
    await demo_university_search()

if __name__ == "__main__":
    asyncio.run(main())