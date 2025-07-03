from webpath import WebPath
from collections import Counter
from datetime import datetime, timedelta

print("=" * 80)
print("---- BEFORE: Using requests + manual everything ----")
print("=" * 80)

before_code = '''import requests
from urllib.parse import urlencode, urljoin
from collections import Counter
from datetime import datetime, timedelta
import time

def analyze_trending_languages_old():
    base_url = "https://api.github.com"
    
    # step 1: build the  search URL with query parameters
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    params = {
        'q': f'created:>{one_week_ago}',
        'sort': 'stars',
        'order': 'desc',
        'per_page': 10
    }
    
    search_url = urljoin(base_url, '/search/repositories')
    query_string = urlencode(params)
    full_url = f"{search_url}?{query_string}"
    
    try:
        # step2: get the trending repos
        resp = requests.get(full_url, headers={'Accept': 'application/vnd.github.v3+json'})
        resp.raise_for_status()
        search_results = resp.json()
        
        language_counts = Counter()
        
        # step3: loop through the results and get 5 
        for repo in search_results.get('items', [])[:5]:
            if repo.get('language'):
                language_counts[repo['language']] += 2
            
            # Step 4: Get contributors URL and fetch
            contributors_url = repo.get('contributors_url')
            if not contributors_url:
                continue
                
            try:
                contrib_resp = requests.get(contributors_url, params={'per_page': 5})
                contrib_resp.raise_for_status()
                contributors = contrib_resp.json()
                
                # last step another loop
                for contributor in contributors[:3]:
                    user_url = contributor.get('url')
                    if not user_url:
                        continue
                    
                    try:
                        user_resp = requests.get(user_url)
                        user_resp.raise_for_status()
                        user_data = user_resp.json()
                        
                        repos_url = user_data.get('repos_url')
                        if not repos_url:
                            continue
                        
                        repos_resp = requests.get(repos_url, params={'per_page': 10, 'sort': 'stars'})
                        repos_resp.raise_for_status()
                        user_repos = repos_resp.json()
                        
                        for repo in user_repos[:5]:
                            if repo.get('language'):
                                language_counts[repo['language']] += 1
                                
                    except requests.RequestException:
                        continue
                        
            except requests.RequestException:
                continue
            
            time.sleep(0.1)  # Be nice to GitHub's API
        
        return language_counts.most_common(10)
        
    except requests.RequestException as e:
        print(f"Error: {e}")
        return []

results = analyze_trending_languages_old()
'''

print(before_code)

print("\n" + "=" * 80)
print("AFTER: Using WebPath (24 lines)")
print("=" * 80)

after_code = '''from webpath import WebPath
from collections import Counter
from datetime import datetime, timedelta

def analyze_trending_languages_new():
    api = WebPath("https://api.github.com")
    
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    trending = (api / "search" / "repositories").with_query(
        q=f'created:>{one_week_ago}',
        sort='stars',
        order='desc',
        per_page=10
    ).get()
    
    language_counts = Counter()
    
    # nav through results naturally
    for i, repo in enumerate(trending['items'][:5]):
        if repo.get('language'):
            language_counts[repo['language']] += 2
        
        contributors = trending / 'items' / i / 'contributors_url'
        for j in range(min(3, len(contributors.json_data))):
            user = contributors / j / 'url'
            user_repos = user / 'repos_url'
            
            for repo in user_repos.json_data[:5]:
                if repo.get('language'):
                    language_counts[repo['language']] += 1
    
    return language_counts.most_common(10)

results = analyze_trending_languages_new()
'''

print(after_code)

print("\n" + "=" * 80)
print("RUNNING THE WEBPATH VERSION")
print("=" * 80)

####################actual wp code to fetch trending languages

api = WebPath("https://api.github.com")

print("\nFetching this week's trending repositories...")
one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
trending = (api / "search" / "repositories").with_query(
    q=f'created:>{one_week_ago} stars:>100',  
    sort='stars',
    order='desc', 
    per_page=20
).get()

languages = Counter()
for repo in trending['items']:
    if repo.get('language'):
        languages[repo['language']] += 1

print(f"\nLanguages in {len(trending['items'])} trending repos:")
for lang, count in languages.most_common(8):
    bar = "*" * (count * 2)
    print(f"{lang:12} {bar} {count}")