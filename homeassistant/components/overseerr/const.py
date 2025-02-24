"""Constants for the overseerr integration."""

import logging

from python_overseerr.models import NotificationType

DOMAIN = "overseerr"
LOGGER = logging.getLogger(__package__)

REQUESTS = "requests"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_STATUS = "status"
ATTR_SORT_ORDER = "sort_order"
ATTR_REQUESTED_BY = "requested_by"

EVENT_KEY = f"{DOMAIN}_event"

REGISTERED_NOTIFICATIONS = (
    NotificationType.REQUEST_PENDING_APPROVAL
    | NotificationType.REQUEST_APPROVED
    | NotificationType.REQUEST_DECLINED
    | NotificationType.REQUEST_AVAILABLE
    | NotificationType.REQUEST_PROCESSING_FAILED
    | NotificationType.REQUEST_AUTOMATICALLY_APPROVED
)
JSON_PAYLOAD = (
    '"{\\"notification_type\\":\\"{{notification_type}}\\",\\"subject\\":\\"{{subject}'
    '}\\",\\"message\\":\\"{{message}}\\",\\"image\\":\\"{{image}}\\",\\"{{media}}\\":'
    '{\\"media_type\\":\\"{{media_type}}\\",\\"tmdb_id\\":\\"{{media_tmdbid}}\\",\\"t'
    'vdb_id\\":\\"{{media_tvdbid}}\\",\\"status\\":\\"{{media_status}}\\",\\"status4k'
    '\\":\\"{{media_status4k}}\\"},\\"{{request}}\\":{\\"request_id\\":\\"{{request_id'
    '}}\\",\\"requested_by_email\\":\\"{{requestedBy_email}}\\",\\"requested_by_userna'
    'me\\":\\"{{requestedBy_username}}\\",\\"requested_by_avatar\\":\\"{{requestedBy_a'
    'vatar}}\\",\\"requested_by_settings_discord_id\\":\\"{{requestedBy_settings_disco'
    'rdId}}\\",\\"requested_by_settings_telegram_chat_id\\":\\"{{requestedBy_settings_'
    'telegramChatId}}\\"},\\"{{issue}}\\":{\\"issue_id\\":\\"{{issue_id}}\\",\\"issue_'
    'type\\":\\"{{issue_type}}\\",\\"issue_status\\":\\"{{issue_status}}\\",\\"reporte'
    'd_by_email\\":\\"{{reportedBy_email}}\\",\\"reported_by_username\\":\\"{{reported'
    'By_username}}\\",\\"reported_by_avatar\\":\\"{{reportedBy_avatar}}\\",\\"reported'
    '_by_settings_discord_id\\":\\"{{reportedBy_settings_discordId}}\\",\\"reported_by'
    '_settings_telegram_chat_id\\":\\"{{reportedBy_settings_telegramChatId}}\\"},\\"{{'
    'comment}}\\":{\\"comment_message\\":\\"{{comment_message}}\\",\\"commented_by_ema'
    'il\\":\\"{{commentedBy_email}}\\",\\"commented_by_username\\":\\"{{commentedBy_us'
    'ername}}\\",\\"commented_by_avatar\\":\\"{{commentedBy_avatar}}\\",\\"commented_b'
    'y_settings_discord_id\\":\\"{{commentedBy_settings_discordId}}\\",\\"commented_by'
    '_settings_telegram_chat_id\\":\\"{{commentedBy_settings_telegramChatId}}\\"}}"'
)
