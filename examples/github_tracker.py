import asyncio
import httpx
from webpath.core import Client, WebPath
from pathlib import Path

def simple_backoff(response):
    if response.status_code >= 500:
        print("Server error detected, retrying in 1 second...")
        return 1.0
    return None

async def inspect_and_archive_repo(owner, repo):
    
    async with Client(
        "https://api.github.com",
        headers={"Accept": "application/vnd.github.v3+json"},
        retries=simple_backoff
    ) as github_api:

        archive_path = Path(f"./{repo}-main.zip")
        try:
            print("Fetching repo details...")
            repo_data = await github_api.aget("repos", owner, repo)

            stargazers_count = repo_data.find("stargazers_count")
            default_branch = repo_data.find("default_branch")
            print(f"Repository has {stargazers_count:,} stargazers. Default branch: {default_branch}")

            zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{default_branch}"
            print(f"Archive URL: {zip_url}")
            
            WebPath(zip_url).download(archive_path)
            
            file_size = archive_path.stat().st_size
            print(f"Repository archive saved to '{archive_path}' ({file_size:,} bytes)")

            all_contributors = (await github_api.aget("repos", owner, repo, "contributors")).paginate_all()
            
            print(f"Found {len(all_contributors)} contributors.")
            
            if all_contributors:
                top_5 = [c['login'] for c in all_contributors[:5]]
                print(f"Top 5 contributors: {', '.join(top_5)}")
            else:
                print("No contributors found.")

        except httpx.HTTPStatusError as e:
            print(f"API request failed: {e.response.status_code}")
            print(f"Error details: {e}")
                
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            if archive_path.exists():
                archive_path.unlink()

if __name__ == "__main__":
    asyncio.run(inspect_and_archive_repo(owner="duriantaco", repo="skylos"))