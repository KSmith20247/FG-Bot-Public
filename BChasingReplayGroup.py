import requests, json
from urllib.parse import urlsplit





API_KEY = N/A

API_GROUP_ENDPOINT = 'https://ballchasing.com/api/groups/'

def get_group_id(group_url):
    path = urlsplit(group_url).path
    parts = path.split('/')
    if len(parts) >= 3:
        return parts[2]
    else:
        print("Invalid group URL.")
        return None

def get_group_stats(group_url):
    group_id = get_group_id(group_url)
    if not group_id:
        return None
    print(f"Group ID: {group_id}")

    headers = {
        'Authorization': f'{API_KEY}'
    }

    api_url = API_GROUP_ENDPOINT + group_id
    print(f"API URL: {api_url}")

    try:
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            file_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot\FG-Bot\data.json"
            with open(file_path, "w", encoding="utf-8") as outfile:
                json.dump(response.json(), outfile, indent=4, ensure_ascii=False)
            match_data = response.json()
            return match_data
        else:
            print(f"Error: {response.status_code} - {response.text}")
    finally:
        print("ran")





#to run as a standalone file with command line input

#group_url = input("\nEnter the BallChasing.com group URL: ")
#group_stats = get_group_stats(group_url)
