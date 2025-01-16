import os
import random

from pathlib import Path
from enum import Enum

AMOUNT_FACTOR = 100


class Contextype(Enum):
    PROTOCOL = 1


def load_dynamic_bg_image():
    BASE_DIR = Path(__file__).resolve().parent.parent
    PATH = os.path.join(BASE_DIR, "static/img/background/")
    filenames = []
    for filename in os.listdir(PATH):
        filenames.append(filename)

    image_url = "img/background/" + filenames[random.randrange(0, len(filenames))]
    return image_url
