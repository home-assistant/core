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
JSON_PAYLOAD = """\
{
    "notification_type": "{{notification_type}}",
    "event": "{{event}}",
    "subject": "{{subject}}",
    "message": "{{message}}",
    "image": "{{image}}",
    "{{media}}": {
        "media_type": "{{media_type}}",
        "imdb_id": "{{media_imdbid}}",
        "tmdb_id": "{{media_tmdbid}}",
        "tvdb_id": "{{media_tvdbid}}",
        "jellyfin_media_id": "{{media_jellyfinMediaId}}",
        "status": "{{media_status}}",
        "status4k": "{{media_status4k}}"
    },
    "{{request}}": {
        "request_id": "{{request_id}}",
        "requested_by_email": "{{requestedBy_email}}",
        "requested_by_username": "{{requestedBy_username}}",
        "requested_by_avatar": "{{requestedBy_avatar}}",
        "requested_by_jellyfin_user_id": "{{requestedBy_jellyfinUserId}}",
        "requested_by_settings_discord_id": "{{requestedBy_settings_discordIds}}",
        "requested_by_settings_telegram_chat_id": "{{requestedBy_settings_telegramChatId}}"
    },
    "{{issue}}": {
        "issue_id": "{{issue_id}}",
        "issue_type": "{{issue_type}}",
        "issue_status": "{{issue_status}}",
        "reported_by_email": "{{reportedBy_email}}",
        "reported_by_username": "{{reportedBy_username}}",
        "reported_by_avatar": "{{reportedBy_avatar}}",
        "reported_by_settings_discord_id": "{{reportedBy_settings_discordIds}}",
        "reported_by_settings_telegram_chat_id": "{{reportedBy_settings_telegramChatId}}"
    },
    "{{comment}}": {
        "comment_message": "{{comment_message}}",
        "commented_by_email": "{{commentedBy_email}}",
        "commented_by_username": "{{commentedBy_username}}",
        "commented_by_avatar": "{{commentedBy_avatar}}",
        "commented_by_settings_discord_id": "{{commentedBy_settings_discordIds}}",
        "commented_by_settings_telegram_chat_id": "{{commentedBy_settings_telegramChatId}}"
    },
    "{{extra}}": []
}"""
