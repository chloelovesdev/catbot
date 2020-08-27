import logging

# adapted from https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

#The background is set with 40 plus the number of the color, and the foreground with 30

#These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

BASH_COLOR_CODES = {
    "RED": COLOR_SEQ % (30 + RED),
    "BLUE": COLOR_SEQ % (30 + BLUE),
    "GREEN": COLOR_SEQ % (30 + GREEN),
    "YELLOW": COLOR_SEQ % (30 + YELLOW),
    "BLUE": COLOR_SEQ % (30 + BLUE),
    "MAGENTA": COLOR_SEQ % (30 + MAGENTA),
    "CYAN": COLOR_SEQ % (30 + CYAN),
    "BOLD": BOLD_SEQ,
    "RESET": RESET_SEQ
}

def bash_color_codes():
    return BASH_COLOR_CODES

def formatter_message(message, use_color = True):
    for color, color_code in BASH_COLOR_CODES.items():
        message = message.replace(f"${color}", color_code)
    
    return message

COLORS = {
    'WARNING': BASH_COLOR_CODES["YELLOW"],
    'INFO': BASH_COLOR_CODES["RESET"],
    'DEBUG': BASH_COLOR_CODES["BLUE"],
    'CRITICAL': BASH_COLOR_CODES["RED"],
    'ERROR': BASH_COLOR_CODES["RESET"] + BASH_COLOR_CODES["RED"]
}

class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, use_color = True):
        logging.Formatter.__init__(self, msg)
        self.use_color = use_color

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            record.levelcolor = COLORS[levelname]
        return logging.Formatter.format(self, record)


def setup_logger(use_colors=True):
    #FORMAT = "[$BOLD%(name)-20s$RESET][%(levelname)-18s]  %(message)s ($BOLD%(filename)s$RESET:%(lineno)d)"
    if not use_colors:
        FORMAT = '[%(asctime)-15s] [%(name)s] %(message)s'
    else:
        FORMAT = formatter_message('$GREEN$BOLD[%(asctime)-15s]$RESET $BLUE$BOLD[%(name)s]$RESET %(levelcolor)s%(message)s$RESET', True)

    sh = logging.StreamHandler()
    sh.setFormatter(ColoredFormatter(FORMAT, use_color=use_colors))

    logging.basicConfig(level=logging.INFO, handlers=[sh], datefmt="%d/%m/%Y %H:%M:%S")