"""Constants for the Twitch integration."""
from logging import Logger, getLogger

ATTR_GAME = "game"
ATTR_TITLE = "title"
ATTR_SUBSCRIBED = "subscribed"
ATTR_SUBSCRIPTION_SINCE = "subscribed_since"
ATTR_SUBSCRIPTION_GIFTED = "subscription_is_gifted"
ATTR_FOLLOWING = "following"
ATTR_FOLLOWING_SINCE = "following_since"
ATTR_FOLLOWERS = "followers"
ATTR_VIEWS = "views"

CONF_CHANNELS = "channels"

DEFAULT_NAME = "Twitch"
DOMAIN = "twitch"
LOGGER: Logger = getLogger(__package__)

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"
