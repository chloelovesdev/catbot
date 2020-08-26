import logging
import os

logger = logging.getLogger(__name__)

class FileBasedFactoidManager:
    def __init__(self, global_store_path):
        # find and create factoid directory
        self.factoid_dir_path = os.path.realpath(os.path.join(global_store_path, "factoids"))
        if not os.path.isdir(self.factoid_dir_path):
            logger.info("Creating factoid directory %s", self.factoid_dir_path)
            os.mkdir(self.factoid_dir_path)

    # currently using files as a "DB"
    def get_path(self, name):
        name = name.replace("/", "").replace(".", "").replace("\\", "")
        return os.path.join(self.factoid_dir_path, name)

    def get_content_binary(self, name):
        factoid_path = self.get_path(name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path, "rb")
            content = factoid_file.read()
            factoid_file.close()
            return content
        else:
            return None
            
    def get_content(self, name):
        factoid_path = self.get_path(name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path, "r")
            content = factoid_file.read()
            factoid_file.close()
            return content
        else:
            return None
        
    def set_content(self, name, content):
        factoid_path = self.get_path(name)
        factoid_file = open(factoid_path, "w")
        factoid_file.write(content)
        factoid_file.close()
        return True
        
    def set_content_binary(self, name, content):
        factoid_path = self.get_path(name)
        factoid_file = open(factoid_path, "wb")
        factoid_file.write(content)
        factoid_file.close()
        return True

    def list_of(self):
        all_factoids = os.listdir(self.factoid_dir_path)
        nonstate_factoids = []

        for factoid in all_factoids:
            if not factoid.startswith("state-"):
                nonstate_factoids.append(factoid)

        nonstate_factoids.sort()
        return nonstate_factoids