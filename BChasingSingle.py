import requests
import re
import json

API_KEY = N/A


API_ENDPOINT = 'https://ballchasing.com/api/replays/'

def seconds_to_clock(seconds):
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

def get_match_stats(match_url):
   
    match_id = re.search(r'replay/([\w-]+)', match_url)
    if not match_id:
        print("Invalid match URL.")
        return None
    match_id = match_id.group(1)

    
    headers = {
        'Authorization': API_KEY
    }

    
    api_url = API_ENDPOINT + match_id

    try:
        
        response = requests.get(api_url, headers=headers)

        
        if response.status_code == 200:
            file_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot\FG-Bot\data.json.txt"
            with open(file_path, "w", encoding="utf-8") as outfile:
                json.dump(response.json(), outfile, indent=4, ensure_ascii=False)
            match_data = response.json()
            return match_data
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    match_url = input("\nEnter the BallChasing.com match URL: ")
    match_stats = get_match_stats(match_url)



    if match_stats:
        

        
        map_name = match_stats.get('map_name', 'N/A')
        print('\n\n\n\n\n')
        print("Match ID:", match_stats.get('id', 'N/A'))
        print("Map Name:", map_name)
        print("Match Date:", match_stats.get('date', 'N/A'))
        duration_seconds = match_stats.get('duration', 0)
        print("Duration (minutes:seconds):", seconds_to_clock(duration_seconds))
        blue_team_goals = match_stats.get('blue', {}).get('stats', {}).get('core', {}).get('goals', 'N/A')
        orange_team_goals = match_stats.get('orange', {}).get('stats', {}).get('core', {}).get('goals', 'N/A')
        print("Blue Team Goals:", blue_team_goals)
        print("Orange Team Goals:", orange_team_goals)
        print("Winner:", "Blue Team" if blue_team_goals > orange_team_goals else "Orange Team")
        print('\n\n\n\n\n')

        
        print("Full API Response:", match_stats)
    else:
        print("Unable to retrieve match stats.")
