
# Installation for Debian 10

Here is an example installation for Debian 10 on a Google Cloud instance.

## Initial dependencies

First we will install some packages which we will be using to build and run catbot.

```
sudo apt-get install python3 python3-pip git build-essential cmake wget git
sudo pip3 install virtualenv
```

## Docker

After that, [I used Docker's official setup guide for Debian which can be found here.](https://docs.docker.com/engine/install/debian/)

```
sudo apt-get remove docker docker-engine docker.io containerd runc
sudo apt-get update
sudo apt-get install apt-transport-https ca-certificates curl gnupg-agent software-properties-common
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
# verify fingerprint with website
sudo add-apt-repository    "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io
sudo docker run hello-world
# verify you get the hello world output
```

## Linux user

Now we're going to set up a user and password for catbot and give it the docker group so it can access the Docker engine.

```
sudo useradd catbot -g docker -s /bin/bash -m
sudo passwd catbot
```

## libolm

Next, we are going to build libolm inside the catbot home directory, as the version on the Debian repository seems to break. [Newer libolm releases can be found here](https://gitlab.matrix.org/matrix-org/olm/-/releases)

```
su catbot
cd

virtualenv catbot_env
. ~/catbot_env/bin/activate
wget https://gitlab.matrix.org/matrix-org/olm/-/archive/3.1.5/olm-3.1.5.tar.gz
tar zxvf olm-3.1.5.tar.gz 
cd olm-3.1.5
cmake . -Bbuild
cmake --build build
cd python
make olm-python3
make install-python3
```

## Installing catbot

Finally, we download clone catbot from it's repository, build the docker images and configure it.
You will have to know a little bit of python to modify the config currently, and soon there will be an input based configuration creator.

```
cd
git clone https://github.com/chloelovesdev/catbot.git
cd catbot

cd docker_files
./build-all.sh

cd ~/catbot
pip3 install -r requirements.txt

cp create_main_config.py create_main_config_local.py
# edit the config defaults to your hearts desire
nano create_main_config_local.py
python3 create_main_config_local.py
```

## Try it out

Now, we should be able to launch catbot. Please note we have to use an LD_LIBRARY_PATH as on Debian 10 things seem to break due to /usr/local/lib/ not being on the LD_LIBRARY_PATH. If anyone has better installation steps, please create an issue or pull request.

```
export LD_LIBRARY_PATH=/home/catbot/olm-3.1.5/build/
python3 run.py MAIN
```

# Starting catbot in future

You might be able to make a bash script for this.

```
su catbot
. ~/catbot_env/bin/activate
cd ~/catbot/
export LD_LIBRARY_PATH=/home/catbot/olm-3.1.5/build/
python3 run.py MAIN
```