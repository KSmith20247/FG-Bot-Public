import json, logging, carball, os
from typing import Callable



async def _parse_carball(replay_path: str, output_directory: str, on_progress: Callable[[str], None] = None) -> None:
    """
    Parses a Rocket League replay located at a given local path and saves the parsed data to a JSON file

    Args:
        path (str): The local path of the replay file to parse
        output_json_path (str): The local path of the JSON file to save the parsed data
        on_progress (Callable[[str], None]): Optional callback function for progress updates
    """
    print(f"Parsing {replay_path} with carball")

    logging.basicConfig(level=logging.DEBUG)  # Set the logging level to DEBUG

    # Extract the replay file name without extension
    replay_file_name = os.path.splitext(os.path.basename(replay_path))[0]

    # Create the output JSON file path dynamically
    output_json_path = os.path.join(output_directory, f"{replay_file_name}_raw_stats.json")

    analysis_manager = carball.analyze_replay_file(replay_path, calculate_intensive_events=True, analysis_per_goal=False, clean=False)
    parsed_data = analysis_manager.get_json_data()

    # Save the parsed data to a JSON file in the same directory with the replay file name
    with open(output_json_path, 'w', encoding="utf-8") as json_file:
        json.dump(parsed_data, json_file, indent=4, ensure_ascii=False)

    return output_json_path


# # Specify the path for the replay file and the desired output JSON file
# replay_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot\FG-Bot\Replay Files\F21990484BB95D261809C083FFA0CD52.replay" #hardcoded
# output_json_path = r"C:\Users\super\Visual Studio Code Projects\FG-Bot\FG-Bot\data2.json" #hardcoded

# # Call the function to parse the replay and save the data to the JSON file
# _parse_carball(replay_path, output_json_path)
# print("done!")

