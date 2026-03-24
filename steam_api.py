import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('STEAM_API_KEY')

def get_steam_backlog(steam_id, max_minutes=60):
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        'key': API_KEY,
        'steamid': steam_id,
        'format': 'json',
        'include_appinfo': 1,             # Using 1 instead of True
        'include_played_free_games': 1    # Using 1 instead of True
    }

    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise ConnectionError(f"Steam API returned status {response.status_code}. Check your API key or try again later.")

    data = response.json()
    games = data.get('response', {}).get('games', [])

    if 'response' not in data:
        raise ConnectionError("Steam API returned an unexpected response. The profile may be private.")
    
    # Steam returns playtime in minutes. < 60 = less than 1 hour.
    backlog = [g for g in games if g.get('playtime_forever', 0) <= max_minutes]
    return backlog


def resolve_vanity_url(vanity_name):
    """Converts a Steam username/custom URL name to a 17-digit SteamID64"""
    url = "http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    params = {
        'key': API_KEY,
        'vanityurl': vanity_name
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data.get('response', {}).get('success') == 1:
        return data['response']['steamid']  # This returns the 17-digit ID!
    return None
    

if __name__ == "__main__":
    # Use your own Steam ID here to test (the long 17-digit number)
    test_id = "76561198885027734" 
    my_backlog = get_steam_backlog(test_id)
    
    print(f"Found {len(my_backlog)} games in the backlog!")
    for game in my_backlog[:5]:  # Print first 5
        print(f"- {game['name']} ({game['playtime_forever']} mins played)")