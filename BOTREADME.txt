Important Notes:
    remember to make commands so team managers can control their team
    when a player is upserted to supabase, also check the team id of the player, if no matching id in "teamid" of a team, then create a team record and do the stats shit
    try turning clean to True in customparsing.py
    bot_is_working_on_active_submission should only be set to false after the proccessing is done, then it can try to process the next submission must check everywhere for it 
    file shouldnt be added to list of files until it is actually sent to supabase?

    instead of sending every unconnected player to both teams i should know what team the unconnected ones are on based off which discord team it was sent to first and all that
    i should be able to just tell which teams the unconnected players are on

    add league player role to every user that registers, make the id the right one
    


Where I left off:
    dont let duplicate submissions happen
    database file for every replay ever submitted, search it if a replay has already been submitted, add the new one that is being submitted. 
    also it has to be from "playlist": "CUSTOM_LOBBY"

    also tweak the supaboos file so it works

    also make some functions into class marked by #class i think

    also fix summary embed. name teams dynamically, display total amount of games in the series, make sure players go to the team they were actually on

    make command to select many teams and give a role to every member. mostly so i can assign div 2 and div 1 roles after open qual. team selecting already made

WITH registration
    make command to control your own team
    

WITH SUBMITTING
    make sure to name teams after the actual team name in submission summary, also display total games next to title like "Series Summary (5 games)" 
    they must submit at least 3 .replay files?
    


for log:
everytime registered users file is saved, it sends the new file with updated changes to the log
combine both logs, and ping the @bot-dev role when there is an error. also include who started the slash command at the start of every logged submission



#BUGS--------------
cant check if there was an error while upserting player stats??

spectators like casters might be picked up as players and need to connect before it can be sent

If players leave before the game is over, stats will not be tracked because I don't think ids are added to game stats
CHECK THAT^

If someone changes their discord account ill need to manually change their id in the json file. ---- possible to make auto refresh on some things

if interaction times out on discord side, (they dont hit a button for 10 mins or more), i need to find a way to remove their submission from the queue and start the next one

Doesnt collect demo information




#BEFORE HOSTING ON SERVER------------

make repeated functions in a class, so its called in different instances (go through every fuction in every file and determine if it needs to be in a class)

make an announcement asking for people to help break the bot, so i can get a lot of testers working out kinks before season really starts
check every command with people using it at the same time
check if i start a slash command, can other people press the buttons? #fixed, press every button once the bot is done though

handle exceptions for network errors and retries to connect to supabase

change all hardcoded file locations. marked most by #path or #hardcoded, but can maybe find by 'r("C:/Users'
make all print statements into the logs, also search all #log. make sure every log says who initiated interaction
go through every comment and check things i left behind. some are IMPORTANT NOTES
make sure only people in the league can use /leagueregistration
dockerize?



#NOTES FOR PPL -------------

    if you need team name changed (misspelling), make a bot support ticket
    you must only use one rocket league account when playing in the league. 
    winning team must use /submitaseries, or else there is a danger of a series being submitted multiple times

    STAFF NOTES
        dont delete or modify team channels or roles manually, it will break everything



#NOW-----------------

    make command to select many teams and give a role to every member. mostly so i can assign div 2 and div 1 roles after open qual. team selecting already made

    discord id's grabbed from registration. associated with team. the first time that team submits a series, create buttons under the submission check and have each player-
    click on their name so their discord ids are associated with their platform id's then the platform id's are associated with the stats/supabase UUID. 

    make buttons disappear if a user moves on past that part. goes for things like /leagueregistration and /submitaseries 

    #fix and configure database
    #registration
    

    #Submit Replays
        #get replay files from user                                     #DONE
        #parse replay                                                   #DONE
        #retrieve/print stats                                           #DONE
        #detect teams
        #send summary to first team                                     #DONE
        #Send summary to opposite reporting team 
        #if cancelled, tell both teams 
        #if submitted, send to supabase, if no error, tell teams




#SEMI-LATER-----------

estimated response time when something is added to the queue?, or just send the statements like 'parsing x file' instead
make mod log/ add a line under all print statements that sends it to the log or error channel
make /help
make timeout errors so commands cant run infinitely
make ways for team captains/managers to edit their teams
player profiles include their cam settings

#make announcement about how everything is custom and new, so if anything doesnt work well we can change it. offer alternative submission proccess. remind about operations tickets for feature
#requests and bug reports





#LATER---------------
might be able to just make the entire submission assembly line a class. seperate instances might be threaded automatically, which would be nice


Custom 6mans integration
react roles 
fantasy teams for the league
own-goal gamemode. would just swap kickoffs and demo spawns