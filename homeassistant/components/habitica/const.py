"""Constants for the habitica integration."""

from homeassistant.const import APPLICATION_NAME, CONF_PATH, __version__

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

ATTR_CONFIG_ENTRY = "config_entry"
ATTR_SKILL = "skill"
ATTR_TASK = "task"
ATTR_DIRECTION = "direction"
ATTR_TARGET = "target"
ATTR_ITEM = "item"
ATTR_TYPE = "type"
ATTR_PRIORITY = "priority"
ATTR_TAG = "tag"
ATTR_KEYWORD = "keyword"
ATTR_REMOVE_TAG = "remove_tag"
ATTR_ALIAS = "alias"
ATTR_PRIORITY = "priority"
ATTR_COST = "cost"
ATTR_NOTES = "notes"
ATTR_UP_DOWN = "up_down"
ATTR_FREQUENCY = "frequency"
ATTR_COUNTER_UP = "counter_up"
ATTR_COUNTER_DOWN = "counter_down"
ATTR_ADD_CHECKLIST_ITEM = "add_checklist_item"
ATTR_REMOVE_CHECKLIST_ITEM = "remove_checklist_item"
ATTR_SCORE_CHECKLIST_ITEM = "score_checklist_item"
ATTR_UNSCORE_CHECKLIST_ITEM = "unscore_checklist_item"
ATTR_REMINDER = "reminder"
ATTR_REMOVE_REMINDER = "remove_reminder"
ATTR_CLEAR_REMINDER = "clear_reminder"
ATTR_CLEAR_DATE = "clear_date"

SERVICE_CAST_SKILL = "cast_skill"
SERVICE_START_QUEST = "start_quest"
SERVICE_ACCEPT_QUEST = "accept_quest"
SERVICE_CANCEL_QUEST = "cancel_quest"
SERVICE_ABORT_QUEST = "abort_quest"
SERVICE_REJECT_QUEST = "reject_quest"
SERVICE_LEAVE_QUEST = "leave_quest"
SERVICE_GET_TASKS = "get_tasks"

SERVICE_SCORE_HABIT = "score_habit"
SERVICE_SCORE_REWARD = "score_reward"

SERVICE_TRANSFORMATION = "transformation"

SERVICE_UPDATE_REWARD = "update_reward"
SERVICE_CREATE_REWARD = "create_reward"
SERVICE_UPDATE_HABIT = "update_habit"
SERVICE_CREATE_HABIT = "create_habit"
SERVICE_UPDATE_TODO = "update_todo"
SERVICE_CREATE_TODO = "create_todo"

DEVELOPER_ID = "4c4ca53f-c059-4ffa-966e-9d29dd405daf"
X_CLIENT = f"{DEVELOPER_ID} - {APPLICATION_NAME} {__version__}"

SECTION_REAUTH_LOGIN = "reauth_login"
SECTION_REAUTH_API_KEY = "reauth_api_key"
SECTION_DANGER_ZONE = "danger_zone"
