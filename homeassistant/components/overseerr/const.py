"""Constants for the overseerr integration."""

import logging

from python_overseerr.models import NotificationType

DOMAIN = "overseerr"
LOGGER = logging.getLogger(__package__)

REQUESTS = "requests"

REGISTERED_NOTIFICATIONS = (
    NotificationType.REQUEST_PENDING_APPROVAL
    | NotificationType.REQUEST_APPROVED
    | NotificationType.REQUEST_DECLINED
    | NotificationType.REQUEST_AVAILABLE
    | NotificationType.REQUEST_PROCESSING_FAILED
    | NotificationType.REQUEST_AUTOMATICALLY_APPROVED
)
JSON_PAYLOAD = '"{\\"notification_type\\":\\"{{notification_type}}\\",\\"event\\":\\"{{event}}\\",\\"subject\\":\\"{{subject}}\\",\\"message\\":\\"{{message}}\\",\\"image\\":\\"{{image}}\\",\\"{{media}}\\":{\\"media_type\\":\\"{{media_type}}\\",\\"tmdbId\\":\\"{{media_tmdbid}}\\",\\"tvdbId\\":\\"{{media_tvdbid}}\\",\\"status\\":\\"{{media_status}}\\",\\"status4k\\":\\"{{media_status4k}}\\"},\\"{{request}}\\":{\\"request_id\\":\\"{{request_id}}\\",\\"requestedBy_email\\":\\"{{requestedBy_email}}\\",\\"requestedBy_username\\":\\"{{requestedBy_username}}\\",\\"requestedBy_avatar\\":\\"{{requestedBy_avatar}}\\",\\"requestedBy_settings_discordId\\":\\"{{requestedBy_settings_discordId}}\\",\\"requestedBy_settings_telegramChatId\\":\\"{{requestedBy_settings_telegramChatId}}\\"},\\"{{issue}}\\":{\\"issue_id\\":\\"{{issue_id}}\\",\\"issue_type\\":\\"{{issue_type}}\\",\\"issue_status\\":\\"{{issue_status}}\\",\\"reportedBy_email\\":\\"{{reportedBy_email}}\\",\\"reportedBy_username\\":\\"{{reportedBy_username}}\\",\\"reportedBy_avatar\\":\\"{{reportedBy_avatar}}\\",\\"reportedBy_settings_discordId\\":\\"{{reportedBy_settings_discordId}}\\",\\"reportedBy_settings_telegramChatId\\":\\"{{reportedBy_settings_telegramChatId}}\\"},\\"{{comment}}\\":{\\"comment_message\\":\\"{{comment_message}}\\",\\"commentedBy_email\\":\\"{{commentedBy_email}}\\",\\"commentedBy_username\\":\\"{{commentedBy_username}}\\",\\"commentedBy_avatar\\":\\"{{commentedBy_avatar}}\\",\\"commentedBy_settings_discordId\\":\\"{{commentedBy_settings_discordId}}\\",\\"commentedBy_settings_telegramChatId\\":\\"{{commentedBy_settings_telegramChatId}}\\"},\\"{{extra}}\\":[]\\n}"'
