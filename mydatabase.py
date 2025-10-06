import json, re, discord

registered_users_file_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot-Beta\FG-Bot-Beta\registeredusers.json" #hardcoded
submitted_games_file_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot-Beta\FG-Bot-Beta\submittedgames.json" #hardcoded


async def load_submitted_games():
    try:
        with open(submitted_games_file_path, 'r') as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}
        #log the error that file failed to load or is empty


async def save_submitted_games(submitted_games):
    with open(submitted_games_file_path, 'w') as file:
        json.dump(submitted_games, file, indent=4)
        #log

async def insert_submitted_game(submitted_games: "dict[str, dict]", raw_game_data: dict):
    # Extract relevant data from game_data
    replay_id = raw_game_data["gameMetadata"]["id"]
    game_playlist = raw_game_data["gameMetadata"]["playlist"]
    players = raw_game_data["players"]

    # Create a record for the game
    record = {
        "replay_id": replay_id,
        "playlist": game_playlist,
        "players": [{
            "player_name": player["name"],
            "platform_id": player["id"]["id"]
        } for player in players]
    }

    # Add the record to submitted_games
    submitted_games[replay_id] = record
    # Assuming you have an asynchronous function to save submitted_games
    await save_submitted_games(submitted_games)
    print(f"Record added for {replay_id}")  # Log message


async def search_for_submitted_game(submitted_games:"dict[str, dict]", replay_id=str):
    if replay_id in submitted_games:
        print(f"Game found for replay ID: {replay_id}")
        return submitted_games[replay_id]
    else:
        print(f"No game found for replay ID {replay_id}")
        return None 



#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


    

async def load_registered_users():
    try:
        with open(registered_users_file_path, 'r') as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}
        #log the error that file failed to load or is empty



async def save_registered_users(registered_users):
    with open(registered_users_file_path, 'w') as file:
        json.dump(registered_users, file, indent=4)
        #log

async def register_user(registered_users = dict, discord_username=None, discord_id=None, team_id=None, platform=None, platform_id=None, supabase_uuid=None, team_name=None, team_catagory_created=None, team_manager = None, team_role = None):
    record = {
        "discord_username": discord_username,
        "discord_id": discord_id,
        "team_id": team_id,
        "platform": platform,
        "platform_id": platform_id,
        "supabase_uuid": supabase_uuid,
        "team_name": team_name,
        "team_catagory_created": team_catagory_created,
        "team_manager" : team_manager,
        "team_role" : team_role
    }
    registered_users[discord_id] = record  # Use discord_id as the key
    await save_registered_users(registered_users)
    print(f"Record added for {discord_id}") #log


async def search_by_discord_username(registered_users = dict, discord_username = str):
    for record in registered_users.values():
        if record["discord_username"] == discord_username:
            print("Record found:")
            print(record)
            return record 
    print(f"No record found for {discord_username}")


async def search_by_discord_id(registered_users = dict, discord_id = int):
    for record in registered_users.values():
        if str(record["discord_id"]) == str(discord_id):
            print("Record found:")
            print(record)
            return record
    print(f"No record found for {discord_id}")


async def search_by_platform_id(registered_users = dict, platform_id = str):
    for record in registered_users.values():
        if record["platform_id"] == platform_id:
            print("Record found:")
            print(record)
            return record
    print(f"No record found for {platform_id}")


async def search_by_team_id(registered_users=dict, team_id=str):
    matching_records = {}
    for user_id, record in registered_users.items():
        if record["team_id"] == team_id:
            print("Record found:")
            print(record)
            matching_records[user_id] = record
    if matching_records:
        return matching_records
    else:
        print(f"No records found for {team_id}")


async def search_by_team_role_id(registered_users=dict, team_role_id=int):
    matching_records = {}
    for user_id, record in registered_users.items():
        if record["team_role"] == team_role_id:
            print("Record found:")
            print(record)
            matching_records[user_id] = record
    if matching_records:
        return matching_records
    else:
        print(f"No records found for {team_role_id}")


async def return_all_team_roles(registered_users=dict):
    list_of_teams = []
    for user_id, record in registered_users.items():
        team_role = record.get("team_role")  # Use .get() to handle potential None values
        if team_role is not None:  # Check if team_role is not None
            if team_role not in list_of_teams:  # Check if team_role is not already in list_of_teams
                print("New Team Id Found:")
                print(record)
                list_of_teams.append(team_role)
    if list_of_teams:
        return list_of_teams
    else:
        print("No records found with a team role")


async def return_all_team_announcement_channels(registered_users: dict, guild: discord.Guild):
    list_of_announcement_channels = []
    list_of_team_role_id = []
    
    for user_id, record in registered_users.items():
        team_category_id = record.get("team_catagory_created")
        if team_category_id is not None:
            team_category = guild.get_channel(int(team_category_id))
            if team_category:
                announcement_channel = discord.utils.get(team_category.channels, name="announcements", type=discord.ChannelType.text)
                if announcement_channel:
                    list_of_announcement_channels.append(announcement_channel.id)
                    team_role = record.get("team_role")
                    if team_role:
                        list_of_team_role_id.append(team_role)

    if list_of_announcement_channels:
        return list_of_announcement_channels, list_of_team_role_id
    else:
        print("No records found with a team category or announcement channel")
        return []


        

async def upsert_user(registered_users, discord_username=None, discord_id=int, team_id = None, platform=None, platform_id=None, supabase_uuid = None, team_name = None, team_catagory_created = None, team_manager = None, team_role=None, force_team_manager = None):
    # Check if the record exists
    existing_record = None
    if discord_id:
        existing_record = await search_by_discord_id(registered_users = registered_users, discord_id= discord_id)
    print(existing_record)
    if existing_record:
        # Update the existing record
        if discord_username:
            existing_record["discord_username"] = discord_username
        if team_id:
            existing_record["team_id"] = team_id
        if platform:
            existing_record["platform"] = platform
        if platform_id:
            existing_record["platform_id"] = platform_id
        if supabase_uuid:
            existing_record["supabase_uuid"] = supabase_uuid
        if team_name:
            existing_record["team_name"] = team_name
        if team_catagory_created:
            existing_record["team_catagory_created"] = team_catagory_created
        if team_manager:
            existing_record["team_manager"] = team_manager
        if team_role:
            existing_record["team_role"] = team_role

        if force_team_manager:
            existing_record["team_manager"] = team_manager

        print(f"Record for {discord_id} updated.")
        #log changes
    else:
        # Add a new record with the provided values
        await register_user(registered_users=registered_users, discord_username=discord_username, discord_id= discord_id, team_id = team_id, platform=platform, platform_id=platform_id, supabase_uuid = supabase_uuid, team_name=team_name, team_catagory_created=team_catagory_created, team_manager=team_manager, team_role=team_role)
        return #no need to save twice
    await save_registered_users(registered_users)


async def get_username_by_id(discord_id, bot):
    user = await bot.fetch_user(discord_id)
    if user:
        return user.name  # You can also use member.display_name if needed
    return None
    #log


async def upsert_user_from_id(registered_users, discord_id, bot, bot_log_channel, bot_error_log_channel):
    discord_username = await get_username_by_id(discord_id, bot)

    if discord_username:
        await upsert_user(registered_users=registered_users, discord_username=discord_username, discord_id=discord_id)
        print(f"User upserted successfully: {discord_username}") 
        await bot_log_channel.send(f"User upserted successfully: <@{discord_id}>")
    else:
        print(f"Unable to find Discord username for ID: {discord_id}")
        await bot_error_log_channel.send(f"Unable to find Discord username for ID: {discord_id}")

async def sanitize_name(player_name):
    # Replace special characters and spaces with underscores
    sanitized_name = re.sub(r'[^\w]', '_', player_name)
    return sanitized_name