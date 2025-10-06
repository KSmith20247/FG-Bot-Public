import discord, asyncio, shutil, os, json, traceback
from discord.ext import commands
from discord.ui import View
from discord import app_commands
from mydatabase import search_by_discord_id, get_username_by_id, upsert_user, load_registered_users, search_by_team_id, search_by_team_role_id, search_by_platform_id
from mydatabase import return_all_team_roles, load_submitted_games, search_for_submitted_game, insert_submitted_game, return_all_team_announcement_channels
from supaboos import SendToSupabase
from BChasingReplayGroup import get_group_stats
from CustomParsing import _parse_carball





bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
token = os.getenv("DISCORD_TOKEN")

queue_folder_queued_submissions = r"C:\Users\super\Visual Studio Code Projects\FG-Bot-Beta\FG-Bot-Beta\Queued Submissions"
registered_users_file_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot-Beta\FG-Bot-Beta\registeredusers.json" #hardcoded

admin_id = 1067684033791787108 #hardcoded
league_player_role_id = 1218567690038284308 #hardcoded add later
beta_tester_id = 1217986841001590804 #hardcoded
director_role_id = 1111036667122429982 #hardcoded 
free_agents_role_id = 1180256301079593032 #hardcoded 

registration_teammates = []
approved_registration_team_name=""

highest_score = 0  

async def log_registered_users():
    with open(registered_users_file_path, 'rb') as file:
        await bot_log_channel.send(file=discord.File(file, filename="Registered Users"))

async def start_active_submission():
    global bot_is_working_on_an_active_submission
    print("ran start active subsmisison")
    # Check if there is an active submission already
    if bot_is_working_on_an_active_submission:
        print("bot is already working on a submission")
        return

    # Find the next folder in the queue
    queue_folder = queue_folder_queued_submissions 
    subfolders = [f.path for f in os.scandir(queue_folder) if f.is_dir()]

    if subfolders:
        next_submission_folder = subfolders[0]  # Assuming folders are named in increasing order
        bot_is_working_on_an_active_submission = True

        # Restart the process with the next submission folder
        await process_submission(next_submission_folder)
    else:
        
        bot_is_working_on_an_active_submission = False


async def process_submission(submission_folder):
    global bot_is_working_on_an_active_submission
    replay_files = [f for f in os.listdir(submission_folder) if f.endswith('.replay')]
    duplicate_games = []
    not_custom_games = []

    user_id, channel_id = await extract_user_and_channel_id(submission_folder)
    user_channel = bot.get_channel(channel_id)

    if not replay_files: # Should be impossible
        # No replay files found
        # Inform the user about the empty submission
        await send_empty_submission_message(user_id, channel_id)
        await clear_old_submissions(folder_path=submission_folder)
        bot_is_working_on_an_active_submission = False
        await start_active_submission()
        #log
        return
    
   
    await bot_log_channel.send(f"Processing new submission from <@{user_id}>")

    for replay_file in replay_files:
        replay_file_path = os.path.join(submission_folder, replay_file)
        with open(replay_file_path, 'rb') as file:
            await bot_log_channel.send(f"File: {replay_file}", file=discord.File(file, filename=replay_file))
        
        duplicate_game_id, custom_game = await process_replay_file(replay_file_path, submission_folder)
        if duplicate_game_id:
            duplicate_games.append(replay_file)
        if custom_game == False:
            not_custom_games.append(replay_file)

    # After processing all games, check for duplicate games
    if duplicate_games:
        duplicate_games_str = ", ".join([f"`{game}`" for game in duplicate_games])
        await user_channel.send(f"<@{user_id}> At least one of the games you tried to submit has already been submitted. Duplicate Game(s):\n{duplicate_games_str}\nIf you still need to, try running the submission again with valid replays")
        await bot_log_channel.send(f"Duplicate game(s) detected from <@{user_id}>: {duplicate_games_str}")
        

    # Check for not custom games
    if not_custom_games:
        custom_games_str = ", ".join([f"`{game}`" for game in not_custom_games])
        await user_channel.send(f"<@{user_id}> At least one of the games you tried to submit was not from a custom lobby. Game(s):\n{custom_games_str}\nTry running the submission again with valid replays")
        await bot_log_channel.send(f"Not custom game(s) detected from <@{user_id}>: {custom_games_str}")
    
    if duplicate_games or not_custom_games:
        await clear_old_submissions(folder_path=submission_folder)
        bot_is_working_on_an_active_submission = False
        return

        
    embed = await display_summary(submission_folder)

    if not embed:
        # No stats generated
        await send_empty_submission_message(user_id, channel_id)
        await clear_old_submissions(folder_path=submission_folder)
        bot_is_working_on_an_active_submission = False
        return 
    
    await send_summary_embed(embed=embed, submission_folder=submission_folder)
    

async def send_empty_submission_message(user_id, channel_id):
    user = await bot.fetch_user(user_id)
    channel = bot.get_channel(channel_id)
    if user and channel:
        await channel.send(f"<@{user_id}> Your submission had no stats. Please ensure your replay files are valid.")

async def extract_user_and_channel_id(submission_folder):
    for file in os.listdir(submission_folder):
        file_path = os.path.join(submission_folder, file)
        if os.path.isfile(file_path) and file.startswith("Submitee_") and file.endswith(".json"):
            parts = file.split('_')
            if len(parts) == 2:
                user_id_str = parts[1].split('.')[0]  # Extract user ID from the filename
                user_id = int(user_id_str)
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    channel_id = data.get("channel_id")
                return user_id, channel_id
    return None, None

async def find_raw_stats_file(submission_folder):
    for filename in os.listdir(submission_folder):
        if filename.endswith("raw_stats.json"):
            file_path = os.path.join(submission_folder, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    raw_stats = json.load(file)
                return raw_stats
            except Exception as e:
                print(f"Error loading raw stats file: {e}")
                #log
                return None
    print("No raw stats file found in the folder.")
    #log
    return None

async def process_replay_file(replay_file_path, submission_folder):
    json_path = await _parse_carball(replay_path=replay_file_path, output_directory= submission_folder) 
    await bot_log_channel.send(f"Replay file proccessed by carball: {replay_file_path}")
    
    duplicate_game_id, custom_game = await go_get_stats(json_path, submission_folder)

    await bot_log_channel.send(f"Game stats retrieved from json: {json_path}")
    return duplicate_game_id, custom_game


async def send_summary_embed(embed, submission_folder):
    user_id, channel_id = await extract_user_and_channel_id(submission_folder)

    view = SummaryView(interaction=discord.Interaction, embed=embed, submission_folder=submission_folder, user_id=user_id, channel_id =channel_id)
    #send summary back to first team that submitted it, in their team channel
    
    channel = bot.get_channel(channel_id)
    await channel.send(f"<@{user_id}>\n**Make sure this information is correct!** If you approve, it will be sent to the second team. ")
    await channel.send(embed=embed, view=view)
    await bot_log_channel.send(embed=embed)

async def send_summary_embed_again(embed, channel, team_role_id, submission_folder, first_team_role):

    view = SecondSummaryView(interaction=discord.Interaction, embed=embed, team_role_id=team_role_id, submission_folder=submission_folder)
    #send to the second team that was in a submission, in their team channel
    await channel.send(f"<@&{team_role_id}> Another Team Submitted a Series Against You!\n**Make sure this information is correct!** If you approve, it will be submitted. ")
    await channel.send(embed=embed, view=view)
    await bot_log_channel.send(embed=embed)
    
    
async def clear_assembly_line():
    folders = [
        queue_folder_queued_submissions
        #queue_folder_active_submissions,
        #queue_folder_old_submissions
    ]

    for folder in folders:
        # Remove the entire folder and its contents
        shutil.rmtree(folder)
        
        # Recreate the empty folder
        os.makedirs(folder)


async def clear_active_submission(source_folder, destination_folder):
    try:
    # Make sure the source and destination folders exist
        if not os.path.exists(source_folder):
            print("No source folder found")
            await bot_error_log_channel.send("No source folder found")
        if not os.path.exists(destination_folder):
            print("No destination folder found")
            await bot_error_log_channel.send("No destination folder found")

        # Get a list of all files in the source folder
        files = os.listdir(source_folder)

        # Move each file to the destination folder
        for file in files:
            source_path = os.path.join(source_folder, file)
            destination_path = os.path.join(destination_folder, file)
            shutil.move(source_path, destination_path)
            print(f"Moved {file} to {destination_folder}")

        print("Files moved successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")


async def clear_old_submissions(folder_path: str):
    global bot_error_log_channel, bot_log_channel 

    # Check if the provided path is a valid directory
    if not os.path.isdir(folder_path):
        await bot_error_log_channel.send("Invalid folder path given.")
        return

    # Get a list of all files in the folder
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    # Check if there are any files in the folder
    if not files:
        await bot_error_log_channel.send("No files found in the folder given.")
        return

    # Iterate through the files and send each one as a message to the log channels
    await bot_log_channel.send("Clearing a submission...")
    for file_name in files:
        file_path = os.path.join(folder_path, file_name)

        # Send to the general log channel
        
        if bot_log_channel:
            with open(file_path, 'rb') as file:
                await bot_log_channel.send(f"File: {file_name}", file=discord.File(file, filename=file_name))  #must delete subfolder and all files once it successfully sends to discord log. 
                #but first, configure active submission route so that the subfolders will be created and named correctly before i try to find them

    await delete_files_in_folder(folder_path, files)
    shutil.rmtree(folder_path)


async def delete_files_in_folder(folder_path, files_to_delete):
    # Check if the directory exists
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Iterate through the list of files and delete each one
        for file_name in files_to_delete:
            file_path = os.path.join(folder_path, file_name)
            try:
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            except OSError as e:
                print(f"Error deleting {file_path}: {e}")
        

async def go_get_stats(replay_file_path, submission_folder):
    global highest_score, player_data
    with open(replay_file_path, 'r', encoding='utf-8') as file:
        replaygroupdata = json.load(file)
    
    try:
        replay_id = replaygroupdata["gameMetadata"]["id"]
        replay_playlist = replaygroupdata["gameMetadata"]["playlist"]
        if replay_playlist == "CUSTOM_LOBBY":
            custom_lobby = True
        else:
            custom_lobby = False

        
        game = await search_for_submitted_game(submitted_games=submitted_games, replay_id=replay_id)
        # Duplicate game found
        if game is not None:
            return replay_id, custom_lobby
        
        if custom_lobby == False:
            return replay_id, custom_lobby
        
        for player_data in replaygroupdata["players"]:

            game_metadata = replaygroupdata["gameMetadata"]
            scores = game_metadata["score"]


            team_0_score = scores["team0Score"]
            team_1_score = scores["team1Score"]

            player_name = player_data["name"]
            #sanitized_name = await sanitize_name(player_name)
            
            # Check if "platform" key exists
            player_platform = player_data.get("platform", "UnknownPlatform")
            
            # Check if "id" key exists within "id"
            platform_id = player_data.get("id", {}).get("id", "UnknownID")

            cumulative_stats = player_data.get("stats", {}) 
            
            possession_stats = cumulative_stats.get("perPossessionStats", "Unknown")


            goals = player_data.get("goals", 0)
            saves = player_data.get("saves", 0)
            assists = player_data.get("assists", 0)
            shots = player_data.get("shots", 0)
            total_points = player_data.get("score", 0)
            time_in_game = player_data.get("timeInGame", {})
            average_hits = possession_stats.get("averageHits", 0)

            boost_stats = cumulative_stats.get("boost", {})
            boost_used = boost_stats.get("boostUsage", 0)
            wasted_usage = boost_stats.get("wastedUsage", 0)

            what_team = "Orange" if player_data.get("isOrange", 0) == 1 else "Blue" 

            average_stats = cumulative_stats.get("averages", {})
            average_speed = average_stats.get("averageSpeed", 0)

            movement_stats = cumulative_stats.get("positionalTendencies", {})
            time_ground = movement_stats.get("timeOnGround", 0)
            time_low_air = movement_stats.get("timeLowInAir", 0)
            time_high_air = movement_stats.get("timeHighInAir", 0)
            time_offensive_third = movement_stats.get("timeInAttackingThird", 0)
            time_neutral_third = movement_stats.get("timeInNeutralThird", 0)
            time_defensive_third = movement_stats.get("timeInDefendingThird", 0)
            
            calculated_win = 0
            calculated_loss = 0
            is_mvp = 0

            if time_low_air > 0 or time_high_air > 0:
                time_air = (time_low_air + time_high_air) 
            else:
                time_air = 0

            if team_0_score > team_1_score:
                if what_team == "Blue":  
                    calculated_win = calculated_win + 1
                    if total_points > highest_score:
                        highest_score = total_points
                        is_mvp = 1
                elif what_team == "Orange":  
                    calculated_loss = calculated_loss + 1

            elif team_0_score < team_1_score:
                if what_team == "Blue":  
                    calculated_loss = calculated_loss + 1
                    if total_points > highest_score:
                        highest_score = total_points
                        is_mvp = 1
                elif what_team == "Orange":  
                    calculated_win = calculated_win + 1

            player_data = {
                'playername': player_name, 
                'platform': player_platform,
                'platformid': platform_id,
                'wins': calculated_win, 
                'seriesmvp': is_mvp, 
                'losses': calculated_loss, 
                'goals': goals, 
                'saves': saves,
                'assists': assists,
                'shots': shots,
                'totalpoints': total_points,
                'averagetouches': average_hits,
                'timeingame': time_in_game,
                'timeair': time_air,
                'timeground': time_ground,
                'boostused': boost_used,
                'boostwasted': wasted_usage, 
                'averagespeed': average_speed,
                'timeoffensivethird' : time_offensive_third,
                'timeneutralthird' : time_neutral_third,
                'timedefensivethird' : time_defensive_third
            }

            await accumulate_series_stats(player_name,player_platform,platform_id,calculated_win,is_mvp,calculated_loss, goals,saves,assists,shots,total_points,average_hits,time_in_game,time_air,
                                  time_ground,boost_used,wasted_usage,average_speed,time_offensive_third,time_neutral_third,time_defensive_third, submission_folder)
            await accumulate_summary_stats(player_name, goals, saves, assists, shots, what_team, team_0_score, team_1_score, platform_id, submission_folder)

            print(player_data)

    except Exception as e:
        error_message = f"Submitaseries Error: \n`{e}`\n\n{traceback.format_exc()}"
        await bot_error_log_channel.send(error_message)

    finally:
        highest_score = 0 #reset highest score after loop of a full game finishes
    
    return None, None
        


async def get_series_stats_from_file(submission_folder):
    # Search for files in the submission subfolder ending with 'series_stats.json'
    for filename in os.listdir(submission_folder):
        if filename.endswith('series_stats.json'):
            series_stats_filepath = os.path.join(submission_folder, filename)
            try:
                with open(series_stats_filepath, 'r') as series_stats_file:
                    series_stats_data = json.load(series_stats_file)
                
                return series_stats_data, series_stats_filepath
            except (FileNotFoundError, json.JSONDecodeError):
                # If file not found or error reading JSON data, return None
                return None, None
            
async def get_summary_stats_from_file(submission_folder):
    # Search for files in the submission subfolder ending with 'series_stats.json'
    for filename in os.listdir(submission_folder):
        if filename.endswith('summary_stats.json'):
            summary_stats_filepath = os.path.join(submission_folder, filename)
            try:
                with open(summary_stats_filepath, 'r') as summary_stats_file:
                    summary_stats_data = json.load(summary_stats_file)
                
                return summary_stats_data, summary_stats_filepath
            except (FileNotFoundError, json.JSONDecodeError):
                # If file not found or error reading JSON data, return None
                return None, None


async def accumulate_series_stats(player_name, player_platform, platform_id, calculated_win, is_mvp, calculated_loss, goals, saves, assists, shots, total_points, average_hits,
                                  time_in_game, time_air, time_ground, boost_used, wasted_usage, average_speed, time_offensive_third, time_neutral_third, time_defensive_third, submission_folder):
    series_stats_data, series_stats_filepath = await get_series_stats_from_file(submission_folder)

    if player_name not in series_stats_data:
        series_stats_data[player_name] = {
            'id': None,
            'platform': player_platform,
            'platformid': platform_id,
            'wins': 0,
            'seriesmvp': 0,
            'losses': 0,
            'goals': 0,
            'saves': 0,
            'assists': 0,
            'shots': 0,
            'totalpoints': 0,
            'averagetouches': 0,
            'timeingame': 0,
            'timeair': 0,
            'timeground': 0,
            'boostused': 0,
            'boostwasted': 0,
            'averagespeed': 0,
            'timeoffensivethird': 0,
            'timeneutralthird': 0,
            'timedefensivethird': 0
        }

    # Update stats with new values
    series_stats_data[player_name]['wins'] += calculated_win
    series_stats_data[player_name]['seriesmvp'] = is_mvp
    series_stats_data[player_name]['losses'] += calculated_loss
    series_stats_data[player_name]['goals'] += goals
    series_stats_data[player_name]['saves'] += saves
    series_stats_data[player_name]['assists'] += assists
    series_stats_data[player_name]['shots'] += shots
    series_stats_data[player_name]['totalpoints'] += total_points
    series_stats_data[player_name]['averagetouches'] += average_hits
    series_stats_data[player_name]['timeingame'] += time_in_game
    series_stats_data[player_name]['timeair'] += time_air
    series_stats_data[player_name]['timeground'] += time_ground
    series_stats_data[player_name]['boostused'] += boost_used
    series_stats_data[player_name]['boostwasted'] += wasted_usage
    series_stats_data[player_name]['averagespeed'] += average_speed
    series_stats_data[player_name]['timeoffensivethird'] += time_offensive_third
    series_stats_data[player_name]['timeneutralthird'] += time_neutral_third
    series_stats_data[player_name]['timedefensivethird'] += time_defensive_third

    # Write updated stats back to the file
    with open(series_stats_filepath, 'w') as series_stats_file:
        json.dump(series_stats_data, series_stats_file, indent=4)




async def accumulate_summary_stats(player_name, goals, saves, assists, shots, what_team, team_0_score, team_1_score, platform_id, submission_folder):
    summary_stats, summary_stats_filepath = await get_summary_stats_from_file(submission_folder=submission_folder)

    if player_name not in summary_stats:
        summary_stats[player_name] = {
            'total_wins': 0,
            'total_losses': 0,
            'total_goals': 0,
            'total_saves': 0,
            'total_assists': 0,
            'total_shots': 0,
            'what_team': what_team,
            'platform_id' : platform_id
        }

    summary_stats[player_name]['total_goals'] += goals
    summary_stats[player_name]['total_saves'] += saves
    summary_stats[player_name]['total_assists'] += assists
    summary_stats[player_name]['total_shots'] += shots

    if team_0_score > team_1_score:
        if what_team == "Blue":
            summary_stats[player_name]['total_wins'] += 1
    elif team_0_score < team_1_score:
        if what_team == "Orange":
            summary_stats[player_name]['total_wins'] += 1

    with open(summary_stats_filepath, 'w') as summary_stats_file:
        json.dump(summary_stats, summary_stats_file, indent=4)

    


async def display_summary(submission_folder):
    summary_stats, summary_stats_filepath = await get_summary_stats_from_file(submission_folder=submission_folder)

    if not summary_stats:
        return False

    # Dictionary to store team wins and stats
    team_stats = {'Blue': {'total_wins': 0, 'players': []}, 'Orange': {'total_wins': 0, 'players': []}}

    # Calculate team wins and collect player stats
    for player_name, stats in summary_stats.items():
        team_name = stats['what_team']
        
        team_stats[team_name]['total_wins'] += stats['total_wins']
        team_stats[team_name]['players'].append(
            {
                'name': player_name,
                'goals': stats['total_goals'],
                'saves': stats['total_saves'],
                'shots': stats['total_shots'],
                'assists': stats['total_assists']
            }
        )
        platform_id = stats['platform_id']
        what_team = stats['what_team']

        # Assuming you have a function to search by platform ID
        record = await search_by_platform_id(registered_users=registered_users, platform_id=platform_id)
        if record is not None:
            # Update team name if applicable
            summary_stats[player_name]['what_team'] = record.get('team_name', what_team)
        

    total_games = (team_stats['Blue']['total_wins'] + team_stats['Orange']['total_wins']) // 3

    embed = discord.Embed(title=f"Series Summary ({total_games} games)", color=discord.Color.green())

    # Replace team names with actual names if applicable
    for team_name, team_info in team_stats.items():
        actual_team_name = summary_stats.get(team_info['players'][0]['name'], {}).get("what_team", team_name)
        if actual_team_name not in ["Blue", "Orange"]:
            team_name = actual_team_name
        embed.add_field(
            name=f"\n{team_name} - Wins: {team_info['total_wins'] // 3}\n",
            value="".join([f"\n**{player['name']}** \nGoals: {player['goals']}, Saves: {player['saves']}, Shots: {player['shots']}, Assists: {player['assists']}" for player in team_info['players']]),
            inline=False
        )

    return embed








    

async def make_player_connect_embed(unconnected_players):
    embed = discord.Embed(title="More Information Needed, Submission Can't Be Sent", color=discord.Color.red())
    embed.add_field(name="Click **YOUR** in game name below. This will connect your accounts, you only need to do this once\n\n*The following players have not connected their discord and rocket league accounts:*\n", value="", inline=False)
    
    for player_record in unconnected_players.values():  # Iterate over the values
        name = player_record["game_name"]  # Access "game_name" from the player record
        embed.add_field(name="\u200b", value=f"{name}\n", inline=False)
        
    return embed

async def get_unconnected_players_game_data(player_stats):
    unconnected_players = {}
    for player_name, player_stats in player_stats.items():
        game_platform_id = player_stats.get('platformid', 'Unknown')
        player_record = await search_by_platform_id(registered_users=registered_users, platform_id=game_platform_id)  
        print(f"\n\n\n{player_record}\n\n\n")
        if player_record is None:   
            record = {
                "game_name": player_name,  # Use player name as game name
                "game_platform_id": game_platform_id
            }
            unconnected_players[game_platform_id] = record
    return unconnected_players


#class
async def send_to_first_team(submission_folder, interaction):
    unconnected_players = {}
    good_to_go = False
    series_stats, series_stats_filepath = await get_series_stats_from_file(submission_folder=submission_folder)
    user_id, channel_id = await extract_user_and_channel_id(submission_folder)

    user_record = await search_by_discord_id(registered_users=registered_users, discord_id=user_id)
    if user_record is not None:
        user_team_id = user_record["team_id"]
        team_role_id = user_record["team_role"]
        if user_team_id is not None:
            team_records = await search_by_team_id(registered_users=registered_users, team_id=user_team_id)
            # Filter out records with a connected platform ID
            for key, record in list(team_records.items()):
                if record["platform_id"] is not None:
                    del team_records[key]
            print(f"Player stats list: \n\n {series_stats}")
            print(f"Here are registered users: \n\n {registered_users}")
            print(f"Here are team records without platform id: \n\n {team_records}")
            user_team_channel_id = int(user_record["team_catagory_created"])
            user_team_channel = bot.get_channel(user_team_channel_id)
        else:
            #player is not on a team, which should be impossible to get here
            await user_team_channel.send(f"<@{user_id}> It appears you arent on a team, which shouldn't be possible. Make a ticket if you want the command to work <#1042485632011870308>")#hardcoded
            await bot_error_log_channel.send(f"<@{user_id}> #player is not on a team, which should be impossible ")
    else: 
        #player is unregistered, which should be impossible to get here
        await user_team_channel.send(f"It appears you arent registered, which shouldn't be possible. Make a ticket if you want the command to work <#1042485632011870308>")#hardcoded
        await bot_error_log_channel.send(f"<@{user_id}> #player is unregistered, which should be impossible")

    if team_records:
        unconnected_players = await get_unconnected_players_game_data(series_stats)
            #they are either unregistered or unconnected
            
            #if they are unregistered, the replays won't be allowed because they didn't sign up properly #should be impossible

            #if they are unconnected, make them connect 
                #if they connect, search for record again
        # else:
        #     supabase_uuid = player_record["supabase_uuid"]
        #     if supabase_uuid is not None:
        #         give_it_to_on_conflict = True
            #if they do have a connected record, it checks for supabase uuid. how do i give the on_conflict the supabase id to compare to the database one? 
            #if they have one it updates
            #if they dont it inserts

    if unconnected_players:
        good_to_go = False
        print("\n\n\nNOT GOOD TO GO\n\n\n")
        print(unconnected_players)
    
    if not unconnected_players:
        good_to_go = True


    if good_to_go == False:
        connect_embed_id = None
        embed = await make_player_connect_embed(unconnected_players=unconnected_players)#log the embed, it lists the players needing to connect in the series
        await bot_log_channel.send(embed=embed)
        view = ConnectView(interaction=discord.Interaction, embed=embed, team_role_id=team_role_id, unconnected_players=unconnected_players, connect_embed_id=connect_embed_id, user_team_channel=user_team_channel, second_team=False, submission_folder= submission_folder)
        await user_team_channel.send(f"<@&{team_role_id}>\n**Important!**\nMake sure every unconnected player on your team that played in the series connects to their account, when everyone has connected click the `Next` button\nIf there is a problem, make a ticket  <#1042485632011870308>")
        connect_embed = await user_team_channel.send(embed=embed, view=view)
        connect_embed_id = connect_embed.id
        view.connect_embed_id = connect_embed_id
        return
    
    if good_to_go == True:
        
        #iterate over every player in playerstats, find the second team. get their team channel and send summary check to them

        for player_name, player_data in series_stats.items():
            platform_id = player_data["platformid"]
            player_record = await search_by_platform_id(registered_users=registered_users, platform_id=platform_id)
            player_team_role_id = player_record["team_role"]
            if player_team_role_id != team_role_id:
                next_team = player_team_role_id
                break
        await interaction.followup.send(f"Series summary was sent to the second team")
        await send_to_second_team(next_team, user_id, submission_folder)



#class
async def send_to_second_team(selected_team, first_team_member, submission_folder):

    first_team_record = await search_by_discord_id(registered_users=registered_users, discord_id=int(first_team_member))
    if first_team_record is not None:
        first_team_channel_id = int(first_team_record["team_catagory_created"])
        first_team_channel = bot.get_channel(first_team_channel_id)
        first_team_role = first_team_record["team_role"]
    else:
        await bot_error_log_channel.send(f"There was a problem with sending to the second team, `first_team_member record` returns `None`\nID: `{first_team_member}`")
        return

    team_records = await search_by_team_role_id(registered_users=registered_users, team_role_id=int(selected_team))

    if team_records:
        print("there are team records")
        first_record = next(iter(team_records.values()))  # Get the first record
        second_team_channel_id = int(first_record["team_catagory_created"])
        second_team_channel = bot.get_channel(second_team_channel_id)
        team_role_id = int(first_record["team_role"])

        # send summary check
        embed = await display_summary(submission_folder)
        await send_summary_embed_again(embed=embed, channel=second_team_channel, team_role_id=team_role_id, submission_folder=submission_folder, first_team_role=first_team_role)
        #wait until send_summary_embed is done

        
    else:
        first_team_channel.send("That team doesn't appear registered yet. Make a ticket\n<#1042485632011870308>")
        await bot_error_log_channel.send(f"<@{first_team_member}> Tried sending a submission to second team `{selected_team}` but there were no records for that team. This should be impossible?")

#class
async def check_second_team(second_team_member, submission_folder, interaction):
    global bot_is_working_on_an_active_submission
    good_to_go = False
    series_stats, series_stats_filepath = await get_series_stats_from_file(submission_folder=submission_folder)
    unconnected_players = {}

    second_team_record = await search_by_discord_id(registered_users=registered_users, discord_id=int(second_team_member))
    if second_team_record is not None:
        second_team_channel_id = int(second_team_record["team_catagory_created"])
        team_role_id = int(second_team_record["team_role"])
        second_team_channel = bot.get_channel(second_team_channel_id)
    else:
        bot_error_log_channel.send(f"There was a problem with checking the second team, `second_team_record` returns `None`\nID: <@`{second_team_member}`>")
        return

    
    unconnected_players = await get_unconnected_players_game_data(series_stats)  

    if unconnected_players:
        good_to_go = False
        print("\n\n\nNOT GOOD TO GO\n\n\n")
        print(unconnected_players)
    
    if not unconnected_players:
        good_to_go = True

    if good_to_go == False:
        connect_embed_id = None
        embed = await make_player_connect_embed(unconnected_players=unconnected_players)#log the embed, it lists the players needing to connect in the series
        await bot_log_channel.send(embed=embed)
        view = ConnectView(interaction=discord.Interaction, embed=embed, team_role_id=team_role_id, unconnected_players=unconnected_players, connect_embed_id=connect_embed_id, user_team_channel=second_team_channel, second_team=True, submission_folder=submission_folder)
        await second_team_channel.send(f"<@&{team_role_id}>\n**Important!**\nMake sure every unconnected player on your team that played in the series connects to their account, when everyone has connected click the `Next` button\nIf there is a problem, make a ticket  <#1042485632011870308>")
        connect_embed = await second_team_channel.send(embed=embed, view=view)
        connect_embed_id = connect_embed.id
        view.connect_embed_id = connect_embed_id
        return

    if good_to_go == True:
        user_id, channel_id = await extract_user_and_channel_id(submission_folder)
        submitaseries_initiator_record = await search_by_discord_id(registered_users=registered_users, discord_id=user_id)
        if submitaseries_initiator_record is None:
             await bot_error_log_channel.send(f"<@{user_id}> Failed during `check_second_team`, user record returns `None`")
             return
        first_team_channel_id = int(submitaseries_initiator_record["team_catagory_created"])
        first_team_channel = bot.get_channel(first_team_channel_id)
        first_team_role = int(submitaseries_initiator_record["team_role"])

        await interaction.followup.send(f"Series submitted successfully! Stats are saved")

        upsert_instance = SendToSupabase(bot=bot, first_team_channel = first_team_channel, first_team_role= first_team_role, second_team_channel=second_team_channel, second_team_role=team_role_id, registered_users=registered_users, submit_initiator=user_id ,series_stats=series_stats)
        possible_errors = await upsert_instance.send_full_series_data_to_supabase() 
        

        if possible_errors:
            #for error in possible_errors:
            await bot_log_channel.send(f"Error from <@{user_id}>")#:\n\n\n{error}\n\n\n")
        else:
            raw_game_data = await find_raw_stats_file(submission_folder=submission_folder)
            await insert_submitted_game(submitted_games=submitted_games, raw_game_data=raw_game_data)
            await clear_old_submissions(folder_path=submission_folder)
            #tell them it upserted successfully
        await start_active_submission()

async def make_manage_team_embed():
    embed = discord.Embed(color=discord.Color.green())
    embed.title = ("Select what to change below")
    embed.description =("*This interaction will timeout in 5 minutes*")
    embed.add_field(name= "Edit Team Managers", value="This command will let you add or remove who can manage your team")
    embed.add_field(name= "Add Team Members", value="This command will let you add who can see this category and submit series")
    embed.add_field(name= "Remove Team Members", value="This command will let you remove me")
    embed.add_field(name= "Rename Team", value="This command will let you rename your team and it's category")

    return embed



class ManageTeam(discord.ui.View):
    def __init__(self, timeout, current_manage_user):
        super().__init__(timeout=timeout)
        self.current_manage_user = current_manage_user

    @discord.ui.button(label="Edit Team Managers", style=discord.ButtonStyle.green)
    async def edit_team_managers(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.current_manage_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        
        team_managers = {}

        user_record = await search_by_discord_id(registered_users=registered_users, discord_id=self.current_manage_user)
        if user_record:
            team_id = user_record.get("team_id")
            if team_id :
                team_records = await search_by_team_id(registered_users=registered_users, team_id=team_id)
                for id, record in team_records.items():
                    manager = record.get("team_manager")
                    if manager:
                        team_managers[id] = record

                view = ManageManagers(timeout=300, interaction=interaction, current_manage_user=self.current_manage_user, default_selected=team_managers, team_records=team_records)
                await view.setup_view()

                await interaction.response.send_message(f"Anyone selected below will be a manager for your team. You may remove or add team managers (Max of 3)\n**WARNING** Anyone selected below will also have the permission to remove YOU as a manager")
                await interaction.channel.send(view=view)
                #disable all buttons
                self.stop()
            else:
                await interaction.response.send_message(f"No team id found for <@{self.current_manage_user}>")
        else:
            await interaction.response.send_message(f"No registered user found for <@{self.current_manage_user}>")
    
    @discord.ui.button(label="Add Team Members", style=discord.ButtonStyle.green)
    async def edit_team_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current_manage_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        
        wanted_members = []
        new_members = []

        await interaction.response.send_message(f"Ping any members you would like to add below. Will timeout in 2 minutes")

        def check(message):
            return message.author == interaction.user and message.channel == interaction.channel

        try:
            message = await bot.wait_for('message', check=check, timeout=120)  # Wait for a message from the user
            mentioned_users = message.mentions  # Get mentioned users from the message
            # Do something with the mentioned users, like adding them to the registration_teammates list
            if message.author != interaction.user:
                await interaction.followup.send("Only the user who initiated the command can provide the list of teammates.")
                return
            for user in mentioned_users:
                wanted_members.append(user.id)
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for user input.")
            return
        
        if not wanted_members:
            await interaction.followup.send("No mentions detected. Rerun the command and ping the people you want to add")
            return

        for member in wanted_members:
            #if they are on a team, make their team manager release them first. 
            #if they are unregistered, register them. 
            #if they have a record, but no team, add them to the team
            member_record = await search_by_discord_id(registered_users=registered_users, discord_id=member)
            if member_record :
                if member_record["team_id"]:
                    #they are on a team
                    await interaction.followup.send(f"You cannot add <@{member}> right now, they are currently on a team")
                    continue #go to next player
                #they are registered but not on a team
                new_members.append(member)
            else:
                #they are unregistered
                new_members.append(member)
                continue

        for member in new_members:
            #upsert all needed team info for a base member
            await upsert_user(registered_users=registered_users, discord_id=member)



    @discord.ui.button(label="Remove Team Members", style=discord.ButtonStyle.green)
    async def edit_team_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current_manage_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
                
        team_managers = {}

        user_record = await search_by_discord_id(registered_users=registered_users, discord_id=self.current_manage_user)
        if user_record:
            team_id = user_record.get("team_id")
            if team_id :
                team_records = await search_by_team_id(registered_users=registered_users, team_id=team_id)
                for id, record in team_records.items():
                    manager = record.get("team_manager")
                    if manager:
                        team_managers[id] = record

                view = ManageMembers(timeout=300, interaction=interaction, current_manage_user=self.current_manage_user, default_selected=team_records, team_records=team_records)
                await view.setup_view()

                await interaction.response.send_message(f"Anyone selected below will be a manager for your team. You may remove or add team managers (Max of 3)\n**WARNING** Anyone selected below will also have the permission to remove YOU as a manager")
                await interaction.channel.send(view=view)
                #disable all buttons
                self.stop()
            else:
                await interaction.response.send_message(f"No team id found for <@{self.current_manage_user}>")
        else:
            await interaction.response.send_message(f"No registered user found for <@{self.current_manage_user}>")
        
    @discord.ui.button(label="Rename Team", style=discord.ButtonStyle.green)
    async def rename_team(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.current_manage_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        
        self.stop()


    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current_manage_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        
        await interaction.response.edit_message(embed=self.embed)
        await interaction.followup.send("It was cancelled")
        self.stop()

class ManageMembers(discord.ui.View):
    def __init__(self, timeout, interaction, current_manage_user, default_selected, team_records):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.current_manage_user = current_manage_user
        self.default_selected = default_selected
        self.team_records = team_records

    async def setup_view(self):
        manage_select = ManageMemberSelect(self.interaction, self.current_manage_user, self.default_selected, self.team_records)
        await manage_select.populate_options()
        self.add_item(manage_select)

        submit_button = SubmitMemberButton(self, manage_select, self.current_manage_user, self.default_selected)
        self.add_item(submit_button)

        cancel_button = CancelMemberButton(self, self.current_manage_user)
        self.add_item(cancel_button)

        


class ManageMemberSelect(discord.ui.Select):
    def __init__(self, interaction, current_manage_user, default_selected, team_records):
        super().__init__(
            placeholder="Select every manager",
            custom_id="manage_select",
            options=["temp","temp1","temp2"],
            min_values=1,
            max_values=3
            
        )
        self.interaction = interaction
        self.current_manage_user = current_manage_user
        self.team_records = team_records
        self.default_selected = default_selected
        self.selected_people = None

    async def populate_options(self):
        print("Populating manage options...")
        processed_ids = set()  # Set to store the IDs that have been processed
        temp_options_count = 3  # Number of temporary options to remove
        
        for id, record in self.default_selected.items():
            if id not in processed_ids:
                user_name = await get_username_by_id(discord_id=id, bot=bot)
                option_label = f"{user_name}"
                option_value = id
                print(f"Adding option: label='{option_label}', value='{option_value}'")
                self.add_option(label=option_label, value=option_value, default=True)
                processed_ids.add(id)

        for id, record in self.team_records.items():
            if id not in processed_ids:
                user_name = await get_username_by_id(discord_id=id, bot=bot)
                option_label = f"{user_name}"
                option_value = id
                print(f"Adding option: label='{option_label}', value='{option_value}'")
                self.add_option(label=option_label, value=option_value)
                processed_ids.add(id)

        if len(self.options) > temp_options_count:
            self.options = self.options[temp_options_count:]

        #get the number of current options (how many team members there currently are)
        #set max options to the number of how many team members they currently have - 3
                

    async def callback(self, interaction: discord.Interaction):
        if self.current_manage_user != interaction.user.id:
            await interaction.response.send_message(f"Don't mess with other people's commands, <@{interaction.user.id}>")
            return

        # Respond with a deferred message
        await interaction.response.defer(ephemeral=False, thinking=False)

        # Store the selected people
        self.selected_people = self.values 


class SubmitMemberButton(discord.ui.Button):
    def __init__(self, manager_view, manage_select, current_manager_user, default_selected):
        super().__init__(style=discord.ButtonStyle.green, label="Submit", row=2)
        self.manage_select = manage_select
        self.manager_view = manager_view
        self.current_manager_user = current_manager_user
        self.previous_managers = default_selected
        self.double_clicked = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_manager_user:
            await interaction.response.send_message(f"Don't mess with other people's commands, <@{interaction.user.id}>")
            return
            
        selected_managers = self.manage_select.selected_people  # Access through an instance
        original_manager = await search_by_discord_id(registered_users, self.current_manager_user)

        if selected_managers is None:
            await interaction.response.send_message("Your team needs a manager bruh", ephemeral=True)
            return

        if original_manager:
            manager_role_id = original_manager["team_manager"]
        else:
            await interaction.response.send_message("This error wasn't your fault, but you appear unregistered. Make a ticket\n<#1042485632011870308>")
            return

        if self.current_manager_user not in [int(manager_id) for manager_id in selected_managers]:
            await interaction.response.send_message("You did not keep yourself selected as a manager. If you click submit again without selecting yourself, you will be removed as a manager", ephemeral=True)
            self.double_clicked = True
            return
            
        guild = interaction.guild
            
        if not guild:
            interaction.response.send_message("This error wasn't your fault. Make a ticket\n<#1042485632011870308>")
            return

        if self.double_clicked:
            if self.current_manager_user not in [int(manager_id) for manager_id in selected_managers]:
                await upsert_user(registered_users=registered_users, discord_id=self.current_manager_user, team_manager=None)
                await log_registered_users()
                member = guild.get_member(self.current_manager_user)
                if member:
                    manager_role = discord.utils.get(member.guild.roles, id=manager_role_id)
                    if manager_role:
                        await member.remove_roles(manager_role)
                        await bot_log_channel.send(f"<@{interaction.user.id}> removed himself as a manager")
                    else:
                        print(f"Manager role with ID {manager_role_id} not found")
                else:
                    print(f"Member with ID {self.current_manager_user} not found")

        removed_managers = []
        for id, record in self.previous_managers.items():
            if str(id) not in selected_managers:
                removed_managers.append(id)
                await upsert_user(registered_users=registered_users, discord_id=int(id), team_manager=None, force_team_manager=True)
                await log_registered_users()
                member = guild.get_member(int(id))
                if member:
                    manager_role = discord.utils.get(member.guild.roles, id=manager_role_id)
                    if manager_role:
                        await member.remove_roles(manager_role)
                    else:
                        print(f"Manager role with ID {manager_role_id} not found")
                else:
                    print(f"Member with ID {self.current_manager_user} not found")
        removed_manager_pings = ", ".join([f"<@{int(manager_id)}>" for manager_id in removed_managers])

        selected_manager_pings = ", ".join([f"<@{int(manager_id)}>" for manager_id in selected_managers])
        for manager_id in selected_managers:
            await upsert_user(registered_users=registered_users, discord_id=int(manager_id), team_manager=int(manager_role_id))
            await log_registered_users()
            member = guild.get_member(int(manager_id))
            if member:
                manager_role = discord.utils.get(member.guild.roles, id=manager_role_id)
                if manager_role:
                    await member.add_roles(manager_role)
                else:
                    print(f"Manager role with ID {manager_role_id} not found for user with ID {manager_id}")
            else:
                print(f"Member with ID {manager_id} not found")

        await bot_log_channel.send(f"<@{interaction.user.id}> made the following users his new managers: {selected_manager_pings}")
        await interaction.response.send_message(f"<@{interaction.user.id}> made changes successfully. Current Manager(s): {selected_manager_pings}")
        if removed_managers:
            await bot_log_channel.send(f"<@{interaction.user.id}> removed the following managers: {removed_manager_pings}")
            await interaction.channel.send(f"<@{interaction.user.id}> removed the following managers: {removed_manager_pings}")
            self.manager_view.stop()
        


class CancelMemberButton(discord.ui.Button):
    def __init__(self, manager_view, current_manager_user):
        super().__init__(label="Cancel", style=discord.ButtonStyle.red, row=2)
        self.manager_view = manager_view
        self.current_manager_user = current_manager_user
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_manager_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        await interaction.response.send_message("User Cancelled")
        print("User canceled manage manager") #debug
        self.manager_view.stop()

class ManageManagers(discord.ui.View):
    def __init__(self, timeout, interaction, current_manage_user, default_selected, team_records):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.current_manage_user = current_manage_user
        self.default_selected = default_selected
        self.team_records = team_records

    async def setup_view(self):
        manage_select = ManageSelect(self.interaction, self.current_manage_user, self.default_selected, self.team_records)
        await manage_select.populate_options()
        self.add_item(manage_select)

        submit_button = SubmitManagerButton(self, manage_select, self.current_manage_user, self.default_selected)
        self.add_item(submit_button)

        cancel_button = CancelManagerButton(self, self.current_manage_user)
        self.add_item(cancel_button)

        


class ManageSelect(discord.ui.Select):
    def __init__(self, interaction, current_manage_user, default_selected, team_records):
        super().__init__(
            placeholder="Select every manager",
            custom_id="manage_select",
            options=["temp","temp1","temp2"],
            min_values=1,
            max_values=3
            
        )
        self.interaction = interaction
        self.current_manage_user = current_manage_user
        self.team_records = team_records
        self.default_selected = default_selected
        self.selected_people = None

    async def populate_options(self):
        print("Populating manage options...")
        processed_ids = set()  # Set to store the IDs that have been processed
        temp_options_count = 3  # Number of temporary options to remove
        
        for id, record in self.default_selected.items():
            if id not in processed_ids:
                user_name = await get_username_by_id(discord_id=id, bot=bot)
                option_label = f"{user_name}"
                option_value = id
                print(f"Adding option: label='{option_label}', value='{option_value}'")
                self.add_option(label=option_label, value=option_value, default=True)
                processed_ids.add(id)

        for id, record in self.team_records.items():
            if id not in processed_ids:
                user_name = await get_username_by_id(discord_id=id, bot=bot)
                option_label = f"{user_name}"
                option_value = id
                print(f"Adding option: label='{option_label}', value='{option_value}'")
                self.add_option(label=option_label, value=option_value)
                processed_ids.add(id)

        if len(self.options) > temp_options_count:
            self.options = self.options[temp_options_count:]
                

    async def callback(self, interaction: discord.Interaction):
        if self.current_manage_user != interaction.user.id:
            await interaction.response.send_message(f"Don't mess with other people's commands, <@{interaction.user.id}>")
            return

        # Respond with a deferred message
        await interaction.response.defer(ephemeral=False, thinking=False)

        # Store the selected people
        self.selected_people = self.values 


class SubmitManagerButton(discord.ui.Button):
    def __init__(self, manager_view, manage_select, current_manager_user, default_selected):
        super().__init__(style=discord.ButtonStyle.green, label="Submit", row=2)
        self.manage_select = manage_select
        self.manager_view = manager_view
        self.current_manager_user = current_manager_user
        self.previous_managers = default_selected
        self.double_clicked = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_manager_user:
            await interaction.response.send_message(f"Don't mess with other people's commands, <@{interaction.user.id}>")
            return
            
        selected_managers = self.manage_select.selected_people  # Access through an instance
        original_manager = await search_by_discord_id(registered_users, self.current_manager_user)

        if selected_managers is None:
            await interaction.response.send_message("Your team needs a manager bruh", ephemeral=True)
            return

        if original_manager:
            manager_role_id = original_manager["team_manager"]
        else:
            await interaction.response.send_message("This error wasn't your fault, but you appear unregistered. Make a ticket\n<#1042485632011870308>")
            return

        if self.current_manager_user not in [int(manager_id) for manager_id in selected_managers]:
            await interaction.response.send_message("You did not keep yourself selected as a manager. If you click submit again without selecting yourself, you will be removed as a manager", ephemeral=True)
            self.double_clicked = True
            return
            
        guild = interaction.guild
            
        if not guild:
            interaction.response.send_message("This error wasn't your fault. Make a ticket\n<#1042485632011870308>")
            return

        if self.double_clicked:
            if self.current_manager_user not in [int(manager_id) for manager_id in selected_managers]:
                await upsert_user(registered_users=registered_users, discord_id=self.current_manager_user, team_manager=None)
                await log_registered_users()
                member = guild.get_member(self.current_manager_user)
                if member:
                    manager_role = discord.utils.get(member.guild.roles, id=manager_role_id)
                    if manager_role:
                        await member.remove_roles(manager_role)
                        await bot_log_channel.send(f"<@{interaction.user.id}> removed himself as a manager")
                    else:
                        print(f"Manager role with ID {manager_role_id} not found")
                else:
                    print(f"Member with ID {self.current_manager_user} not found")

        removed_managers = []
        for id, record in self.previous_managers.items():
            if str(id) not in selected_managers:
                removed_managers.append(id)
                await upsert_user(registered_users=registered_users, discord_id=int(id), team_manager=None, force_team_manager=True)
                await log_registered_users()
                member = guild.get_member(int(id))
                if member:
                    manager_role = discord.utils.get(member.guild.roles, id=manager_role_id)
                    if manager_role:
                        await member.remove_roles(manager_role)
                    else:
                        print(f"Manager role with ID {manager_role_id} not found")
                else:
                    print(f"Member with ID {self.current_manager_user} not found")
        removed_manager_pings = ", ".join([f"<@{int(manager_id)}>" for manager_id in removed_managers])

        selected_manager_pings = ", ".join([f"<@{int(manager_id)}>" for manager_id in selected_managers])
        for manager_id in selected_managers:
            await upsert_user(registered_users=registered_users, discord_id=int(manager_id), team_manager=int(manager_role_id))
            await log_registered_users()
            member = guild.get_member(int(manager_id))
            if member:
                manager_role = discord.utils.get(member.guild.roles, id=manager_role_id)
                if manager_role:
                    await member.add_roles(manager_role)
                else:
                    print(f"Manager role with ID {manager_role_id} not found for user with ID {manager_id}")
            else:
                print(f"Member with ID {manager_id} not found")

        await bot_log_channel.send(f"<@{interaction.user.id}> made the following users his new managers: {selected_manager_pings}")
        await interaction.response.send_message(f"<@{interaction.user.id}> made changes successfully. Current Manager(s): {selected_manager_pings}")
        if removed_managers:
            await bot_log_channel.send(f"<@{interaction.user.id}> removed the following managers: {removed_manager_pings}")
            await interaction.channel.send(f"<@{interaction.user.id}> removed the following managers: {removed_manager_pings}")
            self.manager_view.stop()
        


class CancelManagerButton(discord.ui.Button):
    def __init__(self, manager_view, current_manager_user):
        super().__init__(label="Cancel", style=discord.ButtonStyle.red, row=2)
        self.manager_view = manager_view
        self.current_manager_user = current_manager_user
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_manager_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        await interaction.response.send_message("User Cancelled")
        print("User canceled manage manager") #debug
        self.manager_view.stop()


class RegistrationSelect(discord.ui.Select):
    def __init__(self, server_members, registration_view, current_registration_user):
        initial_members = server_members[:20]  # Initialize with the first 20 members
        super().__init__(
            placeholder="Select or search for members of the team",
            custom_id="add_teammate_select",
            options=[
                discord.SelectOption(label=member.display_name, value=str(member.id))
                for member in initial_members
            ],
            min_values=1,
            max_values=5
        )
        self.server_members = server_members
        self.registration_view = registration_view
        self.current_registration_user = current_registration_user
    
    async def callback(self, interaction: discord.Interaction):
        global registration_teammates
        if interaction.user.id != self.current_registration_user:
            await interaction.response.send_message(f"Don't mess with other people's commands, <@{interaction.user.id}>", ephemeral=True)
            return

        search_query = interaction.data['values'][0]  # Assuming search query is the first selected value
        if search_query == "start_typing":
            return  # Do nothing if the user hasn't started typing

        filtered_members = self.search_members(search_query)
        self.options = [
            discord.SelectOption(label=member.display_name, value=str(member.id))
            for member in filtered_members
        ]

        # Update max_values dynamically based on the length of filtered_members
        self.max_values = min(len(filtered_members), 5)

        registration_teammates = self.values
        await self.registration_view.submit_registration_button(interaction)

    def search_members(self, query: str):
        # Implement your search logic here
        # For example, you can filter members whose display name contains the query
        return [member for member in self.server_members if query.lower() in member.display_name.lower()]





class SubmitRegistrationButton(discord.ui.Button):
    def __init__(self, registration_view):
        super().__init__(style=discord.ButtonStyle.green, label="Submit", row= 2)
        self.registration_view = registration_view

    async def callback(self, interaction: discord.Interaction):
        await self.registration_view.submit_registration_button(interaction)

class CancelRegistrationButton(discord.ui.Button):
    def __init__(self, registration_view, current_registration_user):
        super().__init__(label="Cancel", style=discord.ButtonStyle.red, custom_id="registrationcancelbutton", row=2)
        self.registration_view = registration_view
        self.current_registration_user = current_registration_user
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_registration_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        await interaction.response.send_message("User Cancelled")
        print("User canceled registration") #debug
        self.registration_view.stop()

class RegistrationView(View):
    def __init__(self, interaction: discord.Interaction, current_registration_user):
        super().__init__()
        self.current_registration_user = current_registration_user
        self.message_id = None
        server_members = interaction.guild.members

        self.registration_select = RegistrationSelect(server_members, self, current_registration_user=self.current_registration_user)
        self.add_item(self.registration_select)
        self.add_item(SubmitRegistrationButton(self))  # Pass self here
        self.add_item(CancelRegistrationButton(self, current_registration_user=self.current_registration_user))

        self.interaction = interaction

    async def submit_registration_button(self, interaction: discord.Interaction):
        global approved_registration_team_name

        if interaction.user.id != self.current_registration_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            #if the last 3 messages were this ^ time them out? LMAO
            return
        
        if not registration_teammates:
            await interaction.response.send_message("Please select teammates before submitting.", ephemeral=True)
            return

        
        if str(self.current_registration_user) not in str(registration_teammates):
            registration_teammates.append(self.current_registration_user)

        for teammate in registration_teammates:
            player_record = await search_by_discord_id(registered_users=registered_users, discord_id= teammate)
            if player_record is not None: #if they have a record
                if player_record["team_catagory_created"] is not None: #if they are on a team
                    await interaction.response.send_message(f"<@{teammate}> is already on a team, you cannot register them right now", ephemeral=True)
                    team_channel = bot.get_channel(int(player_record["team_catagory_created"])) #get their team id
                    if team_channel is not None:  # Check if the channel exists
                        try:
                            await team_channel.send(f"<@{teammate}>, <@{self.current_registration_user}> tried to register you for their team. If this is what you want, ask your manager to release you or make a ticket here <#1042485632011870308>")#hardcoded
                            return
                        except discord.errors.HTTPException:
                            await bot_error_log_channel.send(f"Failed to send message to channel {team_channel.id}")
                            await allowed_registration_channel.send(f"There was a connection error with Discord. Try again?")
                            return
                        except Exception as e:
                            await bot_error_log_channel.send(f"An error occurred with registration:\n\n {e}")
                            await allowed_registration_channel.send(f"An error occurred:\n\n {e}.\n\nTry again?")
                            return
                    else:
                        await bot_error_log_channel.send(f"<@504739960750997504> Channel with ID {player_record['team_catagory_created']} does not exist.") #hardcoded to me
                        return


        embed = discord.Embed(title="Registration Confirmation", color=discord.Color.green())
        embed.add_field(name="Team Name", value=approved_registration_team_name)
        embed.add_field(name="Teammates", value=', '.join([f"<@{teammate}>" for teammate in registration_teammates]) if registration_teammates else "No teammates added")

        view = RegistrationApproval(interaction=self.interaction, embed=embed, current_registration_user=self.current_registration_user)

        await interaction.response.edit_message(embed=embed, view=view)
        await bot_log_channel.send(f"<@{self.current_registration_user}> is about to register\n", embed=embed)
    
class RegistrationApproval(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, embed: discord.Embed, current_registration_user):
        super().__init__()
        self.interaction = interaction
        self.current_registration_user = current_registration_user
        self.embed = embed
        
        self.embed.description = f"Hitting approve will make a catagory for your team. You can only do this once"

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.current_registration_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            #if the last 3 messages were this ^ time them out? LMAO
            return
            


        await interaction.response.edit_message(embed=self.embed)
        await interaction.edit_original_response(view=None)
        
        guild = interaction.guild

    
        team_category = await guild.create_category(f'{approved_registration_team_name}')
        team_announcement_channel = await guild.create_text_channel('announcements', category=team_category)
        team_general_channel = await guild.create_text_channel('team-chat', category=team_category)
        
        team_control_role = await guild.create_role(name=f"Manager-{approved_registration_team_name}")
        if team_control_role:
            member = guild.get_member(self.current_registration_user)
            if member:
                await member.add_roles(team_control_role)

        team_role = await guild.create_role(name=f'{approved_registration_team_name}')

        league_player_role = discord.utils.get(member.guild.roles, id=league_player_role_id)

        team_ids = [user["team_id"] for user in registered_users.values()]
        max_team_id = max(team_ids) if team_ids else 0
        new_team_id = max(int(max_team_id), 500) + 1
        generated_id = str(new_team_id)

                    
        for teammate in registration_teammates:
            member = guild.get_member(int(teammate))
            if member:
                await member.add_roles(team_role, league_player_role)#and league_player_role

                member_username = await get_username_by_id(teammate, bot)
                if str(teammate) == str(self.current_registration_user):
                    await upsert_user(registered_users=registered_users, discord_id=self.current_registration_user, team_manager=team_control_role.id)
                await upsert_user(registered_users=registered_users, 
                                  discord_id=teammate, 
                                  discord_username=member_username, 
                                  team_name=approved_registration_team_name, 
                                  team_catagory_created=str(team_general_channel.id), 
                                  team_id=generated_id,
                                  team_role= team_role.id)
                await log_registered_users()
        director_role = discord.utils.get(member.guild.roles, id=director_role_id)

        await team_announcement_channel.set_permissions(director_role, read_messages = True, send_messages = True)
        await team_announcement_channel.set_permissions(team_control_role, read_messages = True, send_messages = True)
        await team_announcement_channel.set_permissions(team_role, read_messages=True, send_messages=False)
        await team_announcement_channel.set_permissions(guild.default_role, read_messages=False)
        await team_general_channel.set_permissions(director_role, read_messages = True, send_messages = True)
        await team_general_channel.set_permissions(team_role, read_messages=True, send_messages=True)
        await team_general_channel.set_permissions(guild.default_role, read_messages=False)


        

        await bot_log_channel.send(f"<@{self.current_registration_user}> registered successfully")
        await interaction.followup.send(f"<@{self.current_registration_user}> \n**Submission success!** Your team is registered <#{team_general_channel.id}>")
        #send instructions
        await team_announcement_channel.send(f"<@&{team_control_role.id}> You can make announcements here and manage your team with `/manageteam`")
        await team_general_channel.send(f"<@&{team_role.id}>\nThis is your team's general chat. To use a private vc, join <#1156358058507780136> and refer to <#1110399418223558686> if you want to know how they work\n**You can submit series you play here with** `/submitaseries` Best of luck in the league!")
        self.stop()
        
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current_registration_user:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
            #if the last 3 messages were this ^ time them out for 1 min? LMAO
        
        await interaction.response.edit_message(embed=self.embed)
        await interaction.followup.send("Submission denied.")
        self.stop()


class SummaryView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, embed: discord.Embed, submission_folder, user_id, channel_id):
        super().__init__()
        self.interaction = interaction
        self.embed = embed
        self.submission_folder = submission_folder
        self.user_id = user_id
        self.channel_id = channel_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        await interaction.response.edit_message(embed=self.embed, view=None)
        await interaction.followup.send(f"<@{self.user_id}> approved the submission.")
        await bot_log_channel.send(f"<@{interaction.user.id}> approved the submission.")
        
        await send_to_first_team(self.submission_folder, interaction)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(f"Dont mess with other people's commands, <@{interaction.user.id}>")
            return
        await interaction.response.edit_message(embed=self.embed, view=None)
        await interaction.followup.send(f"<@{self.user_id}> denied the submission.")
        #log denied and by who
        self.stop()

class SecondSummaryView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, embed: discord.Embed, team_role_id, submission_folder):
        super().__init__()
        self.interaction = interaction
        self.embed = embed
        self.submission_folder = submission_folder
        self.team_role_id = team_role_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.team_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
            return
        
        user_record = await search_by_discord_id(registered_users=registered_users, discord_id=interaction.user.id)
        if user_record is None:
                await interaction.response.send_message(f"You are not registered, if you think this is a mistake make a ticket\n<#1042485632011870308>", ephemeral=True)#hardcoded
                return
        

        await interaction.response.edit_message(embed=self.embed, view=None)
        await interaction.followup.send(f"<@{interaction.user.id}> approved the submission.")
        await bot_log_channel.send(f"<@{interaction.user.id}> approved the submission.")
        await check_second_team(interaction.user.id, self.submission_folder, interaction)
        #then signal to go through player checks
        
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.team_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
            return
        await interaction.response.edit_message(embed=self.embed, view=None)
        await interaction.followup.send(f"<@{interaction.user.id}> denied the submission.")
        await bot_log_channel.send(f"<@{interaction.user.id}> denied the submission.")
        #log denied and by who
        #send back to first team
        self.stop()


class ConnectView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, embed: discord.Embed, team_role_id, unconnected_players, connect_embed_id, user_team_channel, second_team, submission_folder):
        super().__init__()
        self.interaction = interaction
        self.embed = embed
        self.submission_folder = submission_folder
        self.next_embed_id = 0
        self.team_role_id = team_role_id
        self.all_team_ids = []
        self.unconnected_players = unconnected_players
        self.user_team_channel = user_team_channel
        self.connect_embed_id = connect_embed_id
        self.total_connected_from_team_that_submitted = 0
        self.next_button_doubled_checked = False
        self.view = None
        self.view_message = None
        self.view_message_id = None
        self.go_ahead = {}
        self.second_team = second_team

        for index, (game_platform_id, player_info) in enumerate(self.unconnected_players.items(), start=1):
            player_name = player_info['game_name']
            game_platform_id = player_info['game_platform_id']  # Player ID (assuming it's unique)
            custom_id = f"connect_{game_platform_id}_{index}"  # Custom ID based on player ID and index
            button = discord.ui.Button(label=player_name, style=discord.ButtonStyle.blurple, custom_id=custom_id)
            button.callback = self.confirm_connect_button
            self.go_ahead[custom_id] = False
            self.add_item(button)

    async def confirm_connect_button(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]  # Get the custom ID of the button clicked
        game_platform_id, index = custom_id.split('_')[1:]  # Extract player ID and index from the custom ID
        name = None
        for player_info in self.unconnected_players.values():
            if player_info['game_platform_id'] == game_platform_id:
                name = player_info['game_name']
                break
        if name is None:
            await interaction.response.send_message("Player not found.", ephemeral=True)
            return

        if self.team_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
            return

        user_record = await search_by_discord_id(registered_users=registered_users, discord_id=interaction.user.id)
        if user_record is None:
            await interaction.response.send_message(f"You are not registered, if you plan to play in the league make a ticket\n<#1042485632011870308>", ephemeral=True)
            return
        else:
            if user_record["platform_id"] is not None:
                await interaction.response.send_message(f"You already have a connected platform id, if you think this is a problem make a ticket\n<#1042485632011870308>", ephemeral=True)
                return
        
        if not self.go_ahead[custom_id]:  # Check if go_ahead is False
            await interaction.response.send_message(f"Are you sure you want to connect to `{name}`?\nClick `{name}` again to connect.", ephemeral=True)
            self.go_ahead[custom_id] = True  # Set go_ahead to True
        else:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
                    item.disabled = True
            await interaction.response.edit_message(embed=self.embed, view=self)

            for player_info in self.unconnected_players.values():  # Iterate over values
                if player_info['game_platform_id'] == game_platform_id:
                    platform_id = player_info["game_platform_id"]
                    await upsert_user(registered_users=registered_users, discord_id=interaction.user.id, platform_id=platform_id)
                    await log_registered_users()
                    self.total_connected_from_team_that_submitted += 1
                    await bot_log_channel.send(f"<@{interaction.user.id}> connected to `{name}`.")
                    await interaction.followup.send(f"<@{interaction.user.id}> connected to `{name}`.")
                    break




    @discord.ui.button(label="Next", style=discord.ButtonStyle.green, row= 4)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if interaction.user.id != 504739960750997504:
            if interaction.user.id != 1109632790363906148: #hardcoded to my and ablaze user id as override
                await bot_log_channel.send(f"{interaction.user.id} is not smitty")

                if self.team_role_id not in [role.id for role in interaction.user.roles]:
                    await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
                    return
                
                user_record = await search_by_discord_id(registered_users=registered_users, discord_id=interaction.user.id)
                if user_record is None:
                        await interaction.response.send_message(f"You are not registered, if you plan to play in the league make a ticket\n<#1042485632011870308>", ephemeral=True)#hardcoded
                        return
                else:
                    if user_record["platform_id"] is None:
                        await interaction.response.send_message(f"You haven't connected to your Rocket League account yet, if you think this is a problem make a ticket\n<#1042485632011870308>", ephemeral=True)#hardcoded
                        return
                
                if self.total_connected_from_team_that_submitted < 1: #make this 3 again when you are done testing
                    await interaction.response.send_message(f"**Less than 3 players have connected.** Make sure all players on your team connect to their account before moving on. If you think this is a problem, make a ticket here \n<#1042485632011870308>", ephemeral=True)#hardcoded
                    return
                
                if self.next_button_doubled_checked == False:
                    await interaction.response.send_message(f"Are you sure that everyone connected? Subs that played or spectated should also connect if they can", ephemeral=True)
                    self.next_button_doubled_checked = True
                    return
            
        if interaction.user.id == 504739960750997504 or interaction.user.id == 1109632790363906148: #hardcoded to my and ablaze user id as override
            if self.next_button_doubled_checked == False:
                await interaction.response.send_message(f"<@{interaction.user.id}> if you press next again you will **admin-override** the player connect limit") #hardcoded to my user id as override
                self.next_button_doubled_checked = True
                return

        if self.next_button_doubled_checked == True:
            #await interaction.followup.edit_message(message_id= self.connect_embed_id,embed=self.embed, view=None) 
            await interaction.response.send_message(f"<@{interaction.user.id}> Confirmed that everyone connected")
            await bot_log_channel.send(f"<@{interaction.user.id}> Confirmed that everyone connected")
            admin_override = True


            if self.second_team == False:
                #send the next view where they have to click the team they played. 
                await bot_log_channel.send(f"<@{interaction.user.id}> Now trying `NextTeamView`")

                self.all_team_ids = await return_all_team_roles(registered_users=registered_users)

                self.view_message = await self.user_team_channel.send(content=f"<@&{self.team_role_id}>\n**Important!** Select the team this series was played against. You will not need to do this every time")
                self.view_message_id = self.view_message.id
                await bot_log_channel.send(self.view_message_id)

                self.view = NextTeamView(interaction, self.team_role_id, self.all_team_ids, self.view_message_id, self.submission_folder)
                await self.view.setup_view()
                await self.view_message.edit(view=self.view)

            if self.second_team == True:
                await interaction.followup.send(f"Series submitted successfully! Stats are saved")
                series_stats, series_stats_filepath = await get_series_stats_from_file(submission_folder=self.submission_folder)

                user_id, channel_id = await extract_user_and_channel_id(self.submission_folder)
                submitaseries_initiator_record = await search_by_discord_id(registered_users=registered_users, discord_id=user_id)
                if submitaseries_initiator_record is None:
                    await bot_error_log_channel.send(f"<@{user_id}> Failed during `check_second_team`, user record returns `None`")
                    await interaction.followup.send(f"<@{user_id}> Failed during `check_second_team`, user record returns `None`")
                    return
                
                first_team_channel_id = int(submitaseries_initiator_record["team_catagory_created"])
                first_team_channel = bot.get_channel(first_team_channel_id)
                first_team_role = int(submitaseries_initiator_record["team_role"])


                upsert_instance = SendToSupabase(bot=bot, first_team_channel = first_team_channel, first_team_role= first_team_role, second_team_channel=self.user_team_channel, second_team_role= self.team_role_id, registered_users=registered_users, submit_initiator= user_id, series_stats=series_stats)
                possible_errors = await upsert_instance.send_full_series_data_to_supabase() 
                
                
                

                if possible_errors:
                    #for error in possible_errors:
                    await bot_log_channel.send(f"Error from <@{user_id}>")#:\n\n\n{error}\n\n\n")
                else:
                    raw_game_data = await find_raw_stats_file(submission_folder=self.submission_folder)
                    await insert_submitted_game(submitted_games=submitted_games, raw_game_data=raw_game_data)
                    await clear_old_submissions(folder_path=self.submission_folder)
                    #tell them it upserted successfully
                await start_active_submission()

            self.stop()



class NextTeamView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, team_role_id, all_team_ids, view_message_id, submission_folder):
        super().__init__()
        self.team_role_id = team_role_id
        self.all_team_ids = all_team_ids
        self.view_message_id = view_message_id
        self.interaction = interaction
        self.submission_folder = submission_folder

    async def setup_view(self):
        self.team_select = TeamSelect(interaction=self.interaction, server_teams=self.all_team_ids, next_team_view=self, team_role_id=self.team_role_id, view_message_id=self.view_message_id) 
        
        # Populate options for TeamSelect
        await self.team_select.populate_options()

        # Add items to the view
        self.add_item(self.team_select)
        self.add_item(SubmitTeamSelectButton(next_team_view=self, team_role_id=self.team_role_id, view_message_id=self.view_message_id, submission_folder=self.submission_folder)) 
        self.add_item(CancelTeamSelectButton(next_team_view=self, team_role_id=self.team_role_id, view_message_id=self.view_message_id)) 


class TeamSelect(discord.ui.Select):
    def __init__(self, interaction, server_teams, next_team_view, team_role_id, view_message_id):
        super().__init__(
            placeholder="Select the team you played",
            custom_id="all_registered_teams_select",
            options=[],
            min_values=1,
            max_values=1
            #auto_submit = False
        )
        self.interaction = interaction
        self.server_teams = server_teams
        self.next_team_view = next_team_view
        self.team_role_id = team_role_id
        self.team_member_list = []
        self.view_message_id = view_message_id
        self.selected_team = None

    async def populate_options(self):
        print("Populating options...")
        for team_id in self.server_teams:
            if int(team_id) == int(self.team_role_id):
                continue
            role = discord.utils.get(self.interaction.guild.roles, id=team_id)
            if role:
                self.team_member_list = []
                team_records = await search_by_team_role_id(registered_users=registered_users, team_role_id=team_id)
                for platform_id, data in team_records.items():
                    player_name = data["discord_username"]
                    self.team_member_list.append(player_name)
                option_label = f"{role.name} ({', '.join(self.team_member_list)})"
                option_value = str(team_id)
                print(f"Adding option: label='{option_label}', value='{option_value}'")
                self.add_option(label=option_label, value=option_value)

    async def callback(self, interaction: discord.Interaction):
        if self.team_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
            return

        # Respond with a deferred message
        await interaction.response.defer(ephemeral=False, thinking=False)

        # Store the selected team
        self.selected_team = self.values[0]  # Get the first (and only) selected value


class SubmitTeamSelectButton(discord.ui.Button):
    def __init__(self, next_team_view, team_role_id, view_message_id, submission_folder): 
        super().__init__(label="Submit", style=discord.ButtonStyle.green, custom_id="registrationsubmitbutton", row=2)
        self.next_team_view = next_team_view
        self.team_role_id = team_role_id
        self.view_message_id = view_message_id 
        self.submission_folder = submission_folder

    async def callback(self, interaction: discord.Interaction):
        if self.team_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
            return
        await interaction.response.send_message(f"<@{interaction.user.id}> confirmed that <@&{self.team_role_id}> played <@&{self.next_team_view.team_select.selected_team}>.")
        await interaction.followup.send(f"Series summary was sent to the second team")
        print("User submitted team")  # debug
        
        
        # Disable the buttons
        self.view.children[1].disabled = True
        self.view.children[2].disabled = True
        
        # Update the view
        await interaction.followup.edit_message(message_id=self.view_message_id, view=self.view)
        
        # Stop further execution
        self.next_team_view.stop()
        await send_to_second_team(self.next_team_view.team_select.selected_team, interaction.user.id, self.submission_folder)


class CancelTeamSelectButton(discord.ui.Button):
    def __init__(self, next_team_view, team_role_id, view_message_id):  
        super().__init__(label="Cancel", style=discord.ButtonStyle.red, custom_id="registrationcancelbutton", row=2)
        self.next_team_view = next_team_view
        self.team_role_id = team_role_id
        self.view_message_id = view_message_id  

    async def callback(self, interaction: discord.Interaction):
        if self.team_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(f"Don't mess with other team's commands, <@{interaction.user.id}>")
            return
        await interaction.response.send_message("The Submission Was Cancelled")
        print("User canceled registration")  # debug
        
        # Disable the team select
        self.view.children[0].disabled = True
        
        # Remove the buttons
        self.view.children[1].disabled = True
        self.view.children[2].disabled = True
        
        # Update the view
        await interaction.followup.edit_message(message_id=self.view_message_id, view=self.view)
        
        # Stop further execution
        self.next_team_view.stop()
        







@bot.event
async def on_ready():
    print('Bot is now running!')
    global bot_error_log_channel, bot_log_channel, allowed_registration_channel, bot_is_working_on_an_active_submission, registered_users, submitted_games
    bot_error_log_channel = bot.get_channel(1218569018341068820)#hardcoded to main server
    bot_log_channel = bot.get_channel(1218569132518146119)#hardcoded to main server
    allowed_registration_channel = bot.get_channel(1018387464211136582)#hardcoded to general in main server
    bot_is_working_on_an_active_submission = False

    await clear_assembly_line()
    registered_users = await load_registered_users()
    submitted_games = await load_submitted_games()

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)") 
        
    except Exception as e:
        print(e)
        #log





@bot.tree.command(name="leagueregistration", description="Register for the league")
@app_commands.describe(registration_team_name="Enter your team name here")
async def leagueregistration(interaction: discord.Interaction, registration_team_name: str):

    # this command should only be allowed to be activated from #league-general.
    global registration_teammates, approved_registration_team_name
    registration_teammates = []
    current_registration_user = interaction.user.id
    current_channel = interaction.channel.id

    if not (5 <= len(registration_team_name) <= 40):
        await interaction.response.send_message("Team name must be between 5 and 40 characters.", ephemeral=True)
        return
    elif (5 <= len(registration_team_name) <= 40):
        approved_registration_team_name = registration_team_name

    if current_channel != allowed_registration_channel.id:
        await interaction.response.send_message(f"You cannot use this command here! Try again in <#{allowed_registration_channel.id}>", ephemeral=True) 
        return

    user_record = await search_by_discord_id(registered_users=registered_users, discord_id=current_registration_user)
    if user_record is not None:
        await bot_log_channel.send(f"<@{current_registration_user}> tried to register, but that user is already registered")
        await interaction.response.send_message(f"You are already registered! Make a ticket if you think this is incorrect <#1042485632011870308>", ephemeral=True)  # hardcoded to bot support
        return

    await interaction.response.send_message("Ping all of your starters and subs in your next message. Will timeout in 2 minutes")

    # Define a check function to filter messages from the user who initiated the command
    def check(message):
        return message.author == interaction.user and message.channel == interaction.channel

    try:
        message = await bot.wait_for('message', check=check, timeout=120)  # Wait for a message from the user
        mentioned_users = message.mentions  # Get mentioned users from the message
        # Do something with the mentioned users, like adding them to the registration_teammates list
        if message.author != interaction.user:
            await interaction.followup.send("Only the user who initiated the command can provide the list of teammates.")
            return
        for user in mentioned_users:
            registration_teammates.append(user.id)
    except asyncio.TimeoutError:
        await interaction.followup.send("Timed out waiting for user input.")
        return

    if not registration_teammates:
            await interaction.followup.send("Rerun the command and ping your teammates")
            return
    
    if len(registration_teammates) < 3 or len(registration_teammates) > 5:
        await interaction.followup.send("Rerun the command, and select between 3 and 5 teammates including youself. Your team cannot have more than 3 starters or 2 subs")

    
    if str(current_registration_user) not in str(registration_teammates):
        registration_teammates.append(current_registration_user)

    for teammate in registration_teammates:
        player_record = await search_by_discord_id(registered_users=registered_users, discord_id= teammate)
        if player_record is not None: #if they have a record
            if player_record["team_catagory_created"] is not None: #if they are on a team
                await interaction.response.send_message(f"<@{teammate}> is already on a team, you cannot register them right now", ephemeral=True)
                team_channel = bot.get_channel(int(player_record["team_catagory_created"])) #get their team id
                if team_channel is not None:  # Check if the channel exists
                    try:
                        await team_channel.send(f"<@{teammate}>, <@{current_registration_user}> tried to register you for their team. If this is what you want, ask your manager to release you or make a ticket here <#1042485632011870308>")#hardcoded
                        return
                    except discord.errors.HTTPException:
                        await bot_error_log_channel.send(f"Failed to send message to channel {team_channel.id}")
                        await allowed_registration_channel.send(f"There was a connection error with Discord. Try again?")
                        return
                    except Exception as e:
                        await bot_error_log_channel.send(f"An error occurred with registration:\n\n {e}")
                        await allowed_registration_channel.send(f"An error occurred:\n\n {e}.\n\nTry again?")
                        return
                else:
                    await bot_error_log_channel.send(f"<@504739960750997504> Channel with ID {player_record['team_catagory_created']} does not exist.") #hardcoded to me
                    return


    embed = discord.Embed(title="Registration Confirmation", color=discord.Color.green())
    embed.add_field(name="Team Name", value=approved_registration_team_name)
    embed.add_field(name="Teammates", value=', '.join([f"<@{teammate}>" for teammate in registration_teammates]) if registration_teammates else "No teammates added")

    view = RegistrationApproval(interaction=interaction, embed=embed, current_registration_user=current_registration_user)

    await interaction.followup.send(embed=embed, view=view)
    await bot_log_channel.send(f"<@{current_registration_user}> is about to register\n", embed=embed)

    

    # await interaction.response.defer()
    # view = RegistrationView(interaction, current_registration_user=current_registration_user)
    # message = await interaction.followup.send("Registration (Continued)", view=view)
    # view.message_id = message.id  # Store the message ID for later use

    # view.message = message


   
@bot.tree.command(name="submitaseries", description="Submit a series you played in the league")
async def submitaseries(interaction: discord.Interaction):
    current_submitaseries_user = interaction.user.id
    submission_channel_id = interaction.channel.id
    queue_folder = queue_folder_queued_submissions 

    # Define a function to check if the message is from the user who initiated the command
    def check_message(msg):
        if msg.author.id == current_submitaseries_user and msg.channel == interaction.channel:
            return msg

    try:
        user_record = await search_by_discord_id(registered_users=registered_users, discord_id=current_submitaseries_user)
        if user_record is not None:
            if str(user_record["discord_id"]) == str(current_submitaseries_user):
                if user_record["team_catagory_created"] is not None:
                    team_general_channel = int(user_record["team_catagory_created"])
                    if str(submission_channel_id) == user_record["team_catagory_created"]:
                         # Get the number of existing subfolders
                        subfolders = [f.path for f in os.scandir(queue_folder) if f.is_dir()]
                        next_folder_num = len(subfolders) + 1

                        # Create a new subfolder for the current submission
                        submission_folder = os.path.join(queue_folder, str(next_folder_num))
                        os.makedirs(submission_folder)

                        await interaction.response.send_message(f"<@{current_submitaseries_user}> Please attach all replay files in your next message. Will timeout in 5 minutes")
                        try:
                            # Wait for a message from the user within a timeout
                            message = await bot.wait_for('message', check= check_message, timeout=300.0)

                            download_success = False
                            if message.attachments:
                                for attachment in message.attachments:
                                    #have to send at least 3 replays
                                    if attachment.filename.endswith('.replay'):
                                        save_path = os.path.join(submission_folder, attachment.filename)
                                        await attachment.save(fp=save_path)
                                        await interaction.followup.send(f"Downloaded .replay file: {attachment.filename}")
                                        download_success = True
                                    else:
                                        await interaction.followup.send(f"<@{current_submitaseries_user}> You sent something other than a `.replay` file. Restart the command")
                                        return
                                if download_success:
                                    # Create the first JSON file (Submitee_interaction_user_id.json)
                                    submitee_filename = f"Submitee_{interaction.user.id}.json"
                                    submitee_filepath = os.path.join(submission_folder, submitee_filename)
                                    submitee_data = {
                                        "user_id": interaction.user.id,
                                        "channel_id": interaction.channel.id,
                                        "submission_folder": submission_folder,
                                        "attachment_filenames": [attachment.filename for attachment in message.attachments if attachment.filename.endswith('.replay')]
                                    }
                                    with open(submitee_filepath, 'w') as submitee_file:
                                        json.dump(submitee_data, submitee_file, indent=4)

                                    # Create the second JSON file (interaction_user_id_series_stats.json)
                                    series_stats_filename = f"{interaction.user.id}_series_stats.json"
                                    series_stats_filepath = os.path.join(submission_folder, series_stats_filename)
                                    series_stats_data = {}# Add series stats data later
                                    
                                    with open(series_stats_filepath, 'w') as series_stats_file:
                                        json.dump(series_stats_data, series_stats_file, indent=4)

                                    # Create the third JSON file (interaction_user_id_summary_stats.json)
                                    summary_stats_filename = f"{interaction.user.id}_summary_stats.json"
                                    summary_stats_filepath = os.path.join(submission_folder, summary_stats_filename)
                                    summary_stats_data = {}# Add summary stats data later
                                    
                                    with open(summary_stats_filepath, 'w') as summary_stats_file:
                                        json.dump(summary_stats_data, summary_stats_file, indent=4)

                                
                                    await interaction.followup.send(f"<@{current_submitaseries_user}> Your submission has been added to the queue!")
                                    await start_active_submission()
                                else:
                                    await interaction.followup.send(f"<@{current_submitaseries_user}> There seems to be a problem with the download. Make a ticket <#1042485632011870308>") # hardcoded
                                    # log 
                                    return
                            else:
                                await interaction.followup.send(f"<@{current_submitaseries_user}> no files found in the last message. Restart the command")
                                return
                        except asyncio.TimeoutError:
                            await interaction.followup.send(f"<@{current_submitaseries_user}> did not respond with a `.replay` file within the time limit.")
                            return
                    else:
                        await interaction.response.send_message(f"You can't use this command here! Try again in <#{team_general_channel}>", ephemeral=True)
                        return
                else:
                    await interaction.response.send_message(f"<@{current_submitaseries_user}> doesn't appear to be on a team. Please register (`/leagueregistration`) before trying to submit a series")
                    return
            else: 
                await interaction.response.send_message("This is a weird bug :( Make a ticket <#1042485632011870308>") # log # hardcoded to bot support
                # it would only happen if the user who did the slash command doesn't match the user that did the slash command, usually comparing int to str
                return
        else: 
            await interaction.response.send_message(f"<@{current_submitaseries_user}> doesn't appear to be registered. Please register (`/leagueregistration`) before trying to submit a series")
            return
    except Exception as e:
        error_message = f"Submitaseries Error: \n`{e}`\n\n{traceback.format_exc()}"
        await bot_error_log_channel.send(error_message)
        return


#command to mod submit
    

#command to push a announcement to every team announcement channel
@bot.tree.command(name="announcetoteams", description="Sends a message to every League Team announcement channel")
@app_commands.describe(announcement = "The exact message to be sent to every team", ping = "If every team will be pinged or not")
async def announcetoteams(interaction: discord.Interaction, announcement: str, ping: bool):
    member = interaction.guild.get_member(interaction.user.id)
    if admin_id in [role.id for role in member.roles]:
        current_guild = interaction.guild
        announcement_channels, team_roles = await return_all_team_announcement_channels(registered_users, current_guild)
        if announcement_channels:
            for channel in announcement_channels:
                for role in team_roles:
                    team_channel = bot.get_channel(channel)
                    if ping == True:
                        await team_channel.send(f"<@&{role}>\n{announcement}")
                        continue
                    await team_channel.send(announcement)
        else: 
            await interaction.response.send_message("No records found with a team category or announcement channel", ephemeral=True)
    else:
        await interaction.response.send_message("You do not have the required role to use this command.", ephemeral=True)
#in the future, upgrade it to also return every team role and make a toggle if i want to ping every team when i announce it



#command to display stats leaderboard
        

#mod command to update everyone's discord username
        

#command for managers to manage their team
@bot.tree.command(name="manageteam", description="Managers of a team may use this command to make changes")
async def insult(interaction: discord.Interaction):
    current_channel = interaction.channel.id
    record = await search_by_discord_id(registered_users=registered_users, discord_id=interaction.user.id)
    if record["team_manager"] == None:
        await interaction.response.send_message("You do not have permission to use this command! You are not a team manager", ephemeral=True)
        await bot_log_channel.send(f"<@{interaction.user.id}> Tried to use `/manageteam` but they dont have permission")

    if str(current_channel) != record.get("team_catagory_created"):
        team_general_channel = int(record.get("team_catagory_created"))
        await interaction.response.send_message(f"You can't use this command here! Try again in <#{team_general_channel}>", ephemeral=True)
        return

    embed = await make_manage_team_embed()
    view = ManageTeam(timeout= 300, current_manage_user=interaction.user.id)
   
    await interaction.response.send_message(embed=embed, view=view)
        


#command for mod management of a team



#command for mods to list how many teams are registered, and their names
@bot.tree.command(name="listleagueteams", description="Lists every registered team by sending every team role")
async def announcetoteams(interaction: discord.Interaction):
    member = interaction.guild.get_member(interaction.user.id)
    if admin_id in [role.id for role in member.roles]:
        all_teams = await return_all_team_roles(registered_users=registered_users)
        if all_teams:
            all_teams_str = ", ".join([f"\n<@&{team}>" for team in all_teams])
            interaction.response.send_message(f"{all_teams_str}",ephemeral=True)
        else: 
            await interaction.response.send_message("No records found with a team role", ephemeral=True)
    else:
        await interaction.response.send_message("You do not have the required role to use this command.", ephemeral=True)



#command for bot to "act on its own"
@bot.tree.command(name="doesnothing", description="Used in beta version")
async def doesnothing(interaction: discord.Interaction, text: str):
    # Check if the user has the required role
    member = interaction.guild.get_member(interaction.user.id)
    if beta_tester_id in [role.id for role in member.roles]:
        await interaction.response.send_message("Your bidding shall be done, My Lord", ephemeral=True)
        original_channel_id = interaction.channel.id
        original_channel = bot.get_channel(original_channel_id)
        await bot_log_channel.send(f"<@{interaction.user.id}> Said : \n{text}")
        await original_channel.send(f"{text}")
    else:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)


#lists every user with free agent role
@bot.tree.command(name="listfreeagents", description="Lists every free agent")
async def listfreeagents(interaction: discord.Interaction):
    current_guild = interaction.guild
    free_agent_role = discord.utils.get(current_guild.roles, id=free_agents_role_id)

    if free_agent_role is not None:
        embed = discord.Embed(title="Free Agents", color=discord.Color.blue())
        for member in free_agent_role.members:
            embed.add_field(name=member.name,value=member.mention, inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("No free agents found.")

#acts as a reaction role to toggle free agent role    
@bot.tree.command(name="togglefreeagent", description="Toggle the free agent role")
async def togglefreeagent(interaction: discord.Interaction):
    member = interaction.user
    free_agent_role = discord.utils.get(member.guild.roles, id=free_agents_role_id)

    if free_agent_role in member.roles:
        await member.remove_roles(free_agent_role)
        await interaction.response.send_message("You have been removed from the free agents.", ephemeral=True)
    else:
        await member.add_roles(free_agent_role)
        await interaction.response.send_message("You have been added to the free agents.", ephemeral=True)


# @bot.tree.command(name="website", description="Get the link to our website")
# async def website(interaction: discord.Interaction):
#     #Give link as useronly message
#     await interaction.response.send_message("https://www.futuregaming.gg", ephemeral= True)
    
# @bot.tree.command(name="submitballchasingreplaygroup", description="Enter the link to your ballchasing.com group to submit the scores")
# @app_commands.describe(link="Enter the link here")
# async def submitreplaygroup(interaction: discord.Interaction, link: str):
#     #Get link from player and give it to ballchasing API
#     global storedLink
#     storedLink = link
#     get_group_stats(group_url=link)
#     await interaction.response.send_message("Your replay group was submitted successfully!",ephemeral=True)



bot.run(token)
