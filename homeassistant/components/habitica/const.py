"""Constants for the habitica integration."""

from homeassistant.const import CONF_PATH

CONF_API_USER = "api_user"

DEFAULT_URL = "https://habitica.com"
ASSETS_URL = "https://habitica-assets.s3.amazonaws.com/mobileApp/images/"
SITE_DATA_URL = "https://habitica.com/user/settings/siteData"
FORGOT_PASSWORD_URL = "https://habitica.com/forgot-password"
SIGN_UP_URL = "https://habitica.com/register"
HABITICANS_URL = "https://habitica.com/static/img/home-main@3x.ffc32b12.png"

DOMAIN = "habitica"

# service constants
SERVICE_API_CALL = "api_call"
ATTR_PATH = CONF_PATH
ATTR_ARGS = "args"

# event constants
EVENT_API_CALL_SUCCESS = f"{DOMAIN}_{SERVICE_API_CALL}_success"
ATTR_DATA = "data"

MANUFACTURER = "HabitRPG, Inc."
NAME = "Habitica"

UNIT_TASKS = "tasks"

ATTR_CONFIG_ENTRY = "config_entry"
ATTR_SKILL = "skill"
ATTR_TASK = "task"
ATTR_DIRECTION = "direction"
ATTR_TARGET = "target"
ATTR_ITEM = "item"
SERVICE_CAST_SKILL = "cast_skill"
SERVICE_START_QUEST = "start_quest"
SERVICE_ACCEPT_QUEST = "accept_quest"
SERVICE_CANCEL_QUEST = "cancel_quest"
SERVICE_ABORT_QUEST = "abort_quest"
SERVICE_REJECT_QUEST = "reject_quest"
SERVICE_LEAVE_QUEST = "leave_quest"
SERVICE_SCORE_HABIT = "score_habit"
SERVICE_SCORE_REWARD = "score_reward"

SERVICE_TRANSFORMATION = "transformation"


WARRIOR = "warrior"
ROGUE = "rogue"
HEALER = "healer"
MAGE = "wizard"

DEVELOPER_ID = "4c4ca53f-c059-4ffa-966e-9d29dd405daf"
