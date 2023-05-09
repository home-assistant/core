"""The Twitch component."""

from twitchAPI.twitch import AuthScope

DOMAIN = "twitch"
OAUTH_SCOPES = [AuthScope.USER_READ_SUBSCRIPTIONS]
CONF_CHANNELS = "channels"
