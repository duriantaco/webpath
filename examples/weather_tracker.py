import logging
import httpx
import asyncio
from webpath.core import Client
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='weather_reporter.log',
    filemode='w'
)
logger = logging.getLogger("WeatherApp")
print("Logging configured. API requests will save at 'weather_reporter.log'.")

def clear_cache():
    cache_dir = Path.home() / ".webpath" / "cache"
    if cache_dir.exists():
        for cache_file in cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                print(f"Cleared cache file: {cache_file.name}")
            except Exception as e:
                print(f"Could not clear {cache_file.name}: {e}")

def fixed_delay_backoff(response: httpx.Response):
    if response.status_code >= 500:
        logger.warning(f"Server error ({response.status_code}) detected. Retrying in 2 seconds...")
        return 2.0
    return None

async def get_weather_report(latitude, longitude, city):
    clear_cache()
    
    weather_api = Client(
        "https://api.open-meteo.com/v1",
        enable_logging=True,
        retries=2,
        cache_ttl=600
    )

    try:
        weather_response = weather_api.get(
            "forecast",
            latitude=latitude,
            longitude=longitude,
            current_weather="true"
        )
        
        print(f"Weather API Response Status: {weather_response.status_code}")
        print(f"Content-Type: {weather_response.headers.get('content-type', 'unknown')}")
        
        if weather_response.status_code != 200:
            print(f"Weather API Error: {weather_response.text}")
            return
        
        try:
            temperature = weather_response.find("current_weather.temperature", default="N/A")
            wind_speed = weather_response.find("current_weather.windspeed", default="N/A")
            
            print("Current Weather:")
            print(f" - Temperature: {temperature}°C")
            print(f" - Wind Speed: {wind_speed} km/h")
        except Exception as e:
            print(f"Error parsing weather data: {e}")
            print(f"Raw response: {weather_response.text[:200]}")

        air_quality_api = Client("https://air-quality-api.open-meteo.com/v1", enable_logging=True)  # Fixed
        try:
            air_quality_resp = await air_quality_api.aget(
                "air-quality",
                latitude=latitude,
                longitude=longitude,
                current="european_aqi"
            )
            
            print(f"Air Quality API Status: {air_quality_resp.status_code}")
            
            if air_quality_resp.status_code == 200:
                aqi = air_quality_resp.find("current.european_aqi", default="N/A")
                print(f"Air Quality Index (AQI): {aqi}")
            else:
                print("Air Quality: Could not fetch")
                
        except Exception as e:
            print(f"Air quality error: {e}")
        finally:
            air_quality_api.close()
            await air_quality_api.aclose()
        
    except httpx.RequestError as e:
        logger.error(f"Could not connect to weather API: {e}")
        print(f"Error: Could not connect to the weather API. See 'weather_reporter.log' for details.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
    
    finally:
        weather_api.close()
        await weather_api.aclose()

if __name__ == "__main__":
    sg_latitude, sg_longitude = 1.3521, 103.8198
    
    asyncio.run(get_weather_report(sg_latitude, sg_longitude, "Singapore"))

    test_api = Client("https://httpbin.org", retries=fixed_delay_backoff, enable_logging=True)
    try:
        test_api.get("status/503")
    except httpx.HTTPStatusError as e:
        print(f"Request failed: {e.response.status_code}")
    finally:
        test_api.close()

    print("\n--- Reviewing the 'weather_reporter.log' File ---")
    try:
        with open('weather_reporter.log', 'r') as f:
            print(f.read())
    except FileNotFoundError:
        print("Log file not created.")