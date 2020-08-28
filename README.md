# catbot

A [Matrix](https://matrix.org/) bot using the library [matrix-nio](https://github.com/poljar/matrix-nio) and [Docker](https://www.docker.com/) for running sandboxed code, allowing users to write their own factoid commands which can perform any task required. The bot creates a new process every time it is invited to a room, where it can then be configured for that channel by a management interface.

Factoid commands and module commands support input/output redirection between themselves. So, for example, it is possible to do the following:

![Simple redirection example](https://i.imgur.com/ZXFKrNX.png)

Factoids are also shared across all instances of the bot, although, in the future, there may be an management option to have factoids specific for channels.

## Features

1. Bash-like factoid and command input/output redirection
2. Run untrusted code for PHP, Python, JavaScript and Java in Docker containers
3. Create new process with an instance of the bot for each channel it is invited to
4. Manage the instance of the bot from a management server
  * See realtime log output for the bot using WebSockets
  * Start/stop the room's instance of the bot.
  * Manage trusted devices for rooms with E2E (by device ID)
  * Schedule tasks (like cron) to run after every interval (every minute for example)
  * Change authentication settings for your channel's bot.
  * Enable/disable modules for a channel
5. Basic module system
6. Web interface for factoid editing
  * Create, edit and save factoids
  * IDE powered by [ace from cloud9](https://ace.c9.io/)
  * [Test factoids with bot output](https://i.imgur.com/AsQdXdf.png)

## Screenshots

![Factoid editor](https://i.imgur.com/h2wWQMt.png)
![Management dashboard](https://i.imgur.com/kchLAwC.png)

## Factoids

### Command indicators

Factoids are currently stored in files under the "storage/factoids/" directory. Factoids usually start with one of the following command indicators which denote what is going to be run:
```
<python> or [python] - runs Python 3.7.9 code
<js> or [js] - runs JavaScript using node.js
<php> or [php] - run PHP code using latest cli version
<java> or [java] - runs using OpenJDK 16 - *note factoid entry point class must have main and be named "Factoid"*
<cmd>ping - runs any bot command, ping is used here as an example.
```
But any command from a module, or a factoid can be used in the <> or [] brackets and catbot will handle it. More languages will be added later.
There are also various tags for factoids which just contain styling.
```
<html> - Will send to Matrix room using HTML formatting
<markdown> - Will convert markdown to HTML and send to Matrix room
```

### Input redirection

Every command is split using regular expressions by the Bash pipe delimiter "|". If the character is escaped (i.e. \|) then the pipe is ignored and the escape character is removed before the command is fully executed.
Certain commands do not use the regular expressions and as such "eat" all the input. For example, this is used in !factoid set so that the pipes in the factoid content do not interfere with the creation/update of the factoid.

### Bash-like args replacing

Factoids contents also have arguments replaced into them using the standard bash way of numbered variables, i.e. $1 $2. Although, the input will be wrapped in quotes and escaped, for ease of use in code. Take this for example:

![Example](https://i.imgur.com/EQtWH18.png)

Additionally, $@ will be replaced by a string containing all of the input to the factoid.

## Installation

Please note catbot is still under active development and things may change in future.
[There is an installation guide for Debian 10 here.](/INSTALLATION.md)

## Modules and their commands

All commands and factoids start with the **!** prefix. This will be configurable in future. Some of these commands are not runnable on their own and will require you to redirect input from another command or factoid to them.

[code.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/code.py)
```
code (any redirection to this command will print with <pre> html tags)
```

[factoid.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/factoid.py) - handles getting and setting of factoids
```
factoid get <name>
factoid set <name> <content> 
```

[html.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/html.py) - sends the reply to the room as HTML if required
```
html (data from input is sent as HTML)
```

[image.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/image.py) - takes binary image data as input and will upload and send to the matrix room
```
image <extension> 
```

[images.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/images.py) - downloads and uploads a list of image urls to the Matrix room
```
curlimages (data from input is used)
```

[markdown.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/html.py) - sends the reply to the room using Markdown
```
markdown (data from input is converted from Markdown to HTML)
```

[ping.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/ping.py) - a simple command that replies with "Pong!".
```
ping
```

[ready.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/ready.py) - module simply prints "Bot is ready" when the bot is started to the channel it is assigned to.

[sandbox.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/sandbox.py) - Docker sandboxed code which can be ran by the bot
```
python <code>
php <code>
js <code>
java <code>
```

[sprunge.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/sprunge.py) - module that uploads any input to sprunge and replies with a URL. I would not recommend you use this currently as sprunge does not use HTTPS. In future, there will probably be a feature that hosts large output on the aiohttp management server.

[state.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/state.py) - a simple module for saving and loading factoid states to files. [Normally you will use this in a sequence of commands as such.](https://i.imgur.com/HyhAH1h.png)
```
state get <name> - will output the current state
state set <name> - sets the state to the *FIRST LINE* of the input and passes the rest on or sends it to the channel
```

[strip.py](https://github.com/chloelovesdev/catbot/blob/master/catbot/modules/strip.py) - removes trailing spaces and new lines from output
```
strip - strips input
```