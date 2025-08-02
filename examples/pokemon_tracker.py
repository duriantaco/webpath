import asyncio
import httpx
from webpath.core import Client

async def explore_pokemon(pokemon_name):
    print(f"\n--- Exploring Pokémon: {pokemon_name.capitalize()} ---")
    
    poke_api = Client("https://pokeapi.co/api/v2/")

    try:
        pokemon = await poke_api.aget("pokemon", pokemon_name)

        name, pokemon_id, height = pokemon.extract("name", "id", "height")
        print(f"Name: {name.capitalize()} (ID: {pokemon_id}, Height: {height})")

        type_names = pokemon.find_all("types[*].type.name")
        print(f"Types: {', '.join(t.capitalize() for t in type_names)}")

        first_ability_info = pokemon.find("abilities[0].ability")
        if not first_ability_info:
            print("No info found")
            return

        ability_name = first_ability_info.get('name', 'N/A')
        ability_url = first_ability_info.get('url')

        if not ability_url:
            print(f"First ability '{ability_name}' has no detail URL.")
            return

        print(f"Fetching details: '{ability_name}'...")
        ability_details = await Client(ability_url).aget()
        
        description_list = ability_details.find("effect_entries[?language.name=='en'].effect")

        if description_list:
            description = description_list[0].strip()
            print(f"-> Ability Description: {description}")
        else:
            print("-> Ability Description: Not avail")

    except httpx.HTTPStatusError as e:
        print(f"Could not find Pokémon '{pokemon_name}'. Status: {e.response.status_code}")
    except Exception as e:
        print(f"error occurred: {e}")
    finally:
        await poke_api.aclose()


if __name__ == "__main__":
    pokemon_to_find = ["pikachu", "charmander", "gengar", "snorlax"]
    for pokemon in pokemon_to_find:
        asyncio.run(explore_pokemon(pokemon))