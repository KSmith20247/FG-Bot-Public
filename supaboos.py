import os
from supabase import create_client
from dotenv import load_dotenv
from mydatabase import search_by_platform_id, upsert_user


# Load environment variables from .env file
load_dotenv(dotenv_path=r"C:\Users\super\Visual Studio Code Projects\FG-Bot-Beta\FG-Bot-Beta\superenv.env") #hardcoded

# Retrieve the values
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")


# Initialize Supabase client
supabase = create_client(url, key)


#
#
#will need to make it into a class
#
#
class SendToSupabase():
    def __init__(self, bot, first_team_channel, first_team_role, second_team_channel, second_team_role, 
                 registered_users, submit_initiator, series_stats):
        super().__init__()
        self.bot = bot
        self.first_team_channel = first_team_channel
        self.first_team_role = first_team_role
        self.second_team_channel = second_team_channel
        self.second_team_role = second_team_role
        self.registered_users = registered_users
        self.submit_initiator = submit_initiator
        self.series_stats = series_stats
        self.problem = False
        

    async def send_full_series_data_to_supabase(self):
        stats_to_exclude = ['averagetouches', 'winpercentage', 'shootingpercentage', 'averagepointspergame', 'percentoffensivethird', 'percentneutralthird', 'percentdefensivethird', 'boostperminute', 'averagespeedpercentage']

        for player_name, player_stats in self.series_stats.items():
            game_platform_id = player_stats.get('platformid', 'Unknown')
            player_record = await search_by_platform_id(registered_users=self.registered_users, platform_id=game_platform_id)

            if player_record is None:
                self.problem = True
                await self.first_team_channel.send(f"<@&{self.first_team_role}> There was a problem with the submission from {self.submit_initiator}.\n{player_name} doesn't appear connected to a rocket league account.\nIf {player_name} is on your team, when `/submitaseries` is rerun, make sure they connect.")
                await self.second_team_channel.send(f"<@&{self.second_team_role}> There was a problem with the submission from {self.submit_initiator}.\n{player_name} doesn't appear connected to a rocket league account.\nIf {player_name} is on your team, when `/submitaseries` is rerun, make sure they connect.")
                continue  # Go to the next player

            supabase_uuid = player_record.get("supabase_uuid")

            if supabase_uuid:
                # Fetch the current player stats
                response = supabase.table('s3players').select('*').eq('id', supabase_uuid).execute()
                current_stats_list = response.data  # Get the list of stats
                if response.data :
        
                    # Access the dictionary inside the list (assuming there's only one)
                    current_stats = current_stats_list[0]

                    # # Adjust the value of 'averagetouches' if it exists
                    # if 'averagetouches' in current_stats:
                    #     current_stats['averagetouches'] = 11  # Adjust the value as needed

                    for stat, value in player_stats.items():
                        if stat in current_stats and isinstance(value, (int, float)):
                            if stat == 'averagetouches':
                                current_stats[stat] = (current_stats[stat] + value) / 2
                            elif stat not in stats_to_exclude:
                                current_stats[stat] += value
                    



                # Upsert the updated stats
                    print(f"\n\n\n\n\n\nStats im upserting:\n{current_stats}\n\n\n")
                    response1 = supabase.table('s3players').upsert([current_stats]).execute()


                    if 'error' in response1:
                        error_message1 = response1['error']
                        print(f"Error for {player_name}: \n{error_message1}")
                        #log the error
                    else:
                        print(f"Data for {player_name} inserted0 successfully:\n{response1}")
                        #log success
            else:
                response2 = supabase.table('s3players').select('*').eq('platformid', game_platform_id).execute()

                data = response2.data
                print(f"\n\n\n\n\nPLayerstats:\n{player_stats}\n\n\n\n\n{data}")

                if 'error' in response2:
                    print(f"Error occurred: {response2['error']}")
                else:
                    if data:
                        await upsert_user(registered_users=self.registered_users, discord_id=player_record.get("discord_id"), supabase_uuid=data[0]['id'])

                        # Update player_stats with supabase UUID
                        player_stats['id'] = data[0]['id']

                        # Fetch the current player stats
                        current_stats = data[0]

                        # Update the stats
                        for stat, value in player_stats.items():
                            if stat in current_stats and isinstance(value, (int, float)):
                                if stat == 'averagetouches':
                                    current_stats[stat] = (current_stats[stat] + value) / 2
                                elif stat not in stats_to_exclude:
                                    current_stats[stat] += value

                        # Perform upsert operation for the current player's stats
                        response3 =  supabase.table('s3players').upsert([current_stats]).execute()
                        if 'error' in response3:
                            error_message3 = response3['error']
                            print(f"Error for {player_name}: \n{error_message3}")
                            #log the error
                        else:
                            print(f"Data for {player_name} inserted1 successfully:\n{response3}")
                            #log success
                    else:
                        response4 =  supabase.table('s3players').insert([player_stats]).execute()
                        if 'error' in response4:
                            error_message4 = response4['error']
                            print(f"Error for {player_name}: \n{error_message4}")
                            #log the error
                        else:
                            print(f"Data for {player_name} inserted2 successfully:\n{response4}")
                            #log success

        if self.problem == True:
            return True

        




    
    #await start_active_submission()
    #upsert_user(discord_username, discord_id, player_platform, platform_id, supabase_uuid)  
            





    #when a player is upserted, also check the team id of the player, if no matching id in "teamid" of a team, then create a team and do the stats shit


# well if there will be stats for a player it will come from a 3v3 rocket league match where the teams are identified. i will know all 6 players individually, 
#but i will also know what team they are playing for. i could create something with the discord bot that for any team signing up, it would grab the discord user ids from the players on the team. 
#then i can use their player ids, to help upload all their data which also contains their platform id. once they are uploaded for the first time they will then have a supabase UUID created, 
#and i can store a little array in python that associates all those ids that shouldnt change often with each other.

#  when a player is about to be uploaded, using the platform id from the matches played, i can associate that with a discord account, which will be associated with a supabase UUID. if there is no UUID,
#I insert, if there is UUID, i update. 

