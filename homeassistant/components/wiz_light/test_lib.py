import yaml
import os

with open(r"bulblibrary.yaml") as f:
    dataMap = yaml.safe_load(f)

SUPPORT_BRIGHTNESS = 1
SUPPORT_COLOR_TEMP = 2
SUPPORT_EFFECT = 4
SUPPORT_FLASH = 8
SUPPORT_COLOR = 16
SUPPORT_TRANSITION = 32
SUPPORT_WHITE_VALUE = 128

features = 0
if dataMap["ESP03_SHRGB1W_01"]["features"].get("brightness"):
    features = features | SUPPORT_BRIGHTNESS

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
print(__location__)
