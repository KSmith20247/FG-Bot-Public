Quick note: this project was completed in its entirety BEFORE I had taken any programming classes. At this point, I was completely self taught in class design, modularity, and organization. So structurally, nothing is organized but it does function. 

This project implements a discord bot for our frontend ui, allowing players to register and manage their team, upload replays, and see their stats for each game or lifetime. 
I used supabase for a postgres database to organize the registered players and their game/team stats from tournaments. 
It has a local .replay parsing library to turn .replay files into readable json, this is where i extract the relevant statistics and upsert to my database. 
It also can use the ballchasing.com api to get the json files for each game, but that was not the primary option due to their replay upload limits. 
