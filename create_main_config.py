from python_json_config.config_node import ConfigNode
import os, json

# get our regular paths
global_store_path = os.path.realpath("storage/")
if not os.path.isdir(global_store_path):
    os.mkdir(global_store_path)

main_store_path = os.path.realpath(os.path.join(global_store_path, "MAIN"))
if not os.path.isdir(main_store_path):
    os.mkdir(main_store_path)

config_path = os.path.join(main_store_path, "config.json")

# give our config data
bot_config = ConfigNode({})
bot_config.add("server.url", "https://loves.shitposting.chat")
bot_config.add("server.user_id", "@bot:loves.shitposting.chat")
bot_config.add("server.stored_for_user_id", "@bot:loves.shitposting.chat")
bot_config.add("server.device_name", "BOT")
bot_config.add("server.channel", "!oJGvNtRRSfsLjUOqjv:loves.shitposting.chat")
bot_config.add("server.password", "<PASSWORD>")

bot_config.add("invite_join", False) # bot joins upon invite?
bot_config.add("management_url", "http://localhost:8080")

bot_config.add("trust", {"@chloe:loves.shitposting.chat": ["TJXGVHDQYT"]})

# dump the config's dictionary
config_as_json = json.dumps(bot_config.to_dict(), indent=4)

# save it to a file
config_file = open(config_path, "w")
config_file.write(config_as_json)
config_file.close()