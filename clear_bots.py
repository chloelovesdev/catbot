from python_json_config import ConfigBuilder
import os
import json

builder = ConfigBuilder()
config_path = os.path.realpath("./storage/MAIN/config.json")

bot_config = builder.parse_config(config_path)
bot_config.update("bots", {})

# dump the config's dictionary
config_as_json = json.dumps(bot_config.to_dict())

# save it to a file
config_file = open(config_path, "w")
config_file.write(config_as_json)
config_file.close()

print("file written")
print(config_path)