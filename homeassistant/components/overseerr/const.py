"""Constants for the overseerr integration."""

import logging

from python_overseerr.models import NotificationType

DOMAIN = "overseerr"
LOGGER = logging.getLogger(__package__)

REQUESTS = "requests"

ATTR_MEDIA_TYPE = "media_type"
ATTR_QUERY = "query"
ATTR_REQUESTED_BY = "requested_by"
ATTR_SEASONS = "seasons"
ATTR_STATUS = "status"
ATTR_SORT_ORDER = "sort_order"
ATTR_MEDIA_ID = "media_id"


EVENT_KEY = f"{DOMAIN}_event"

REGISTERED_NOTIFICATIONS = (
    NotificationType.REQUEST_PENDING_APPROVAL
    | NotificationType.REQUEST_APPROVED
    | NotificationType.REQUEST_DECLINED
    | NotificationType.REQUEST_AVAILABLE
    | NotificationType.REQUEST_PROCESSING_FAILED
    | NotificationType.REQUEST_AUTOMATICALLY_APPROVED
    | NotificationType.ISSUE_REPORTED
    | NotificationType.ISSUE_COMMENTED
    | NotificationType.ISSUE_RESOLVED
    | NotificationType.ISSUE_REOPENED
)
# fmt: off
JSON_PAYLOAD = (
    '{\n'
    '    \"notification_type\": \"{{notification_type}}\",\n'
    '    \"event\": \"{{event}}\",\n'
    '    \"subject\": \"{{subject}}\",\n'
    '    \"message\": \"{{message}}\",\n'
    '    \"image\": \"{{image}}\",\n'
    '    \"{{media}}\": {\n'
    '        \"media_type\": \"{{media_type}}\",\n'
    '        \"imdb_id\": \"{{media_imdbid}}\",\n'
    '        \"tmdb_id\": \"{{media_tmdbid}}\",\n'
    '        \"tvdb_id\": \"{{media_tvdbid}}\",\n'
    '        \"jellyfin_media_id\": \"{{media_jellyfinMediaId}}\",\n'
    '        \"status\": \"{{media_status}}\",\n'
    '        \"status4k\": \"{{media_status4k}}\"\n'
    '    },\n'
    '    \"{{request}}\": {\n'
    '        \"request_id\": \"{{request_id}}\",\n'
    '        \"requested_by_email\": \"{{requestedBy_email}}\",\n'
    '        \"requested_by_username\": \"{{requestedBy_username}}\",\n'
    '        \"requested_by_avatar\": \"{{requestedBy_avatar}}\",\n'
    '        \"requested_by_jellyfin_user_id\": \"{{requestedBy_jellyfinUserId}}\",\n'
    '        \"requested_by_settings_discord_id\": \"{{requestedBy_settings_discordIds}}\",\n'
    '        \"requested_by_settings_telegram_chat_id\": \"{{requestedBy_settings_telegramChatId}}\"\n'
    '    },\n'
    '    \"{{issue}}\": {\n'
    '        \"issue_id\": \"{{issue_id}}\",\n'
    '        \"issue_type\": \"{{issue_type}}\",\n'
    '        \"issue_status\": \"{{issue_status}}\",\n'
    '        \"reported_by_email\": \"{{reportedBy_email}}\",\n'
    '        \"reported_by_username\": \"{{reportedBy_username}}\",\n'
    '        \"reported_by_avatar\": \"{{reportedBy_avatar}}\",\n'
    '        \"reported_by_settings_discord_id\": \"{{reportedBy_settings_discordIds}}\",\n'
    '        \"reported_by_settings_telegram_chat_id\": \"{{reportedBy_settings_telegramChatId}}\"\n'
    '    },\n'
    '    \"{{comment}}\": {\n'
    '        \"comment_message\": \"{{comment_message}}\",\n'
    '        \"commented_by_email\": \"{{commentedBy_email}}\",\n'
    '        \"commented_by_username\": \"{{commentedBy_username}}\",\n'
    '        \"commented_by_avatar\": \"{{commentedBy_avatar}}\",\n'
    '        \"commented_by_settings_discord_id\": \"{{commentedBy_settings_discordIds}}\",\n'
    '        \"commented_by_settings_telegram_chat_id\": \"{{commentedBy_settings_telegramChatId}}\"\n'
    '    },\n'
    '    \"{{extra}}\": []\n'
    '}'
)
# fmt: on
