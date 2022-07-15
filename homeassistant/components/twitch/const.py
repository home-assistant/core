"""Constants for the Twitch integration."""
from twitchAPI.twitch import AuthScope

DOMAIN = "twitch"

OAUTH2_AUTHORIZE = "https://id.twitch.tv/oauth2/authorize"
OAUTH2_TOKEN = "https://id.twitch.tv/oauth2/token"
OAUTH_SCOPES = [AuthScope.USER_READ_SUBSCRIPTIONS]

CONF_CHANNELS = "channels"
CONF_REFRESH_TOKEN = "refresh_token"
