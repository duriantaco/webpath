from webpath import WebPath

def test_jsonplaceholder_users():
    print("Testing JSON Shortcuts with JSONPlaceholder API (Users)\n")
    
    api = WebPath("https://jsonplaceholder.typicode.com").with_logging()
    
    response = (api / "users").get()
    
    print("Using .find() for nested user data:")
    
    for i in range(3):
        name = response.find(f"{i}.name")
        email = response.find(f"{i}.email")
        city = response.find(f"{i}.address.city")
        company = response.find(f"{i}.company.name")
        website = response.find(f"{i}.website")
        
        print(f"User {i+1}: {name}")
        print(f"Email: {email}")
        print(f"City: {city}")
        print(f"Company: {company}")
        print(f"Website: {website}")
        print()

def test_jsonplaceholder_posts():
    api = WebPath("https://jsonplaceholder.typicode.com").with_logging()
    
    response = (api / "posts").get()
    
    print(f"\nFound {len(response.json_data)} posts")
    
    all_titles = response.find_all("*.title")
    print("\nFirst 5 post titles:")
    for i, title in enumerate(all_titles[:5]):
        print(f"{i+1}. {title}")

def test_single_user():
    api = WebPath("https://jsonplaceholder.typicode.com").with_logging()
    
    response = (api / "users" / "1").get()
    
    lat = response.find("address.geo.lat")
    lng = response.find("address.geo.lng")
    
    print(f"Name: {response.find('name')}")
    print(f"Coordinates: {lat}, {lng}")

if __name__ == "__main__":
    test_jsonplaceholder_users()
    test_jsonplaceholder_posts() 
    test_single_user()