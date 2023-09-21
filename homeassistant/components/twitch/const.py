"""Const for Twitch."""
import logging

from twitchAPI.twitch import AuthScope

LOGGER = logging.getLogger(__package__)

CONF_CHANNELS = "channels"

OAUTH_SCOPES = [AuthScope.USER_READ_SUBSCRIPTIONS]
