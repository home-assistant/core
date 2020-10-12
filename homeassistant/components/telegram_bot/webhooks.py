"""Support for Telegram bots using webhooks."""
import datetime as dt
from ipaddress import ip_address
import logging

from telegram.error import TimedOut

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    HTTP_BAD_REQUEST,
    HTTP_UNAUTHORIZED,
)
from homeassistant.helpers.network import get_url

from . import (
    CONF_ALLOWED_CHAT_IDS,
    CONF_TRUSTED_NETWORKS,
    CONF_URL,
    BaseTelegramBotEntity,
    initialize_bot,
)

_LOGGER = logging.getLogger(__name__)

TELEGRAM_HANDLER_URL = "/api/telegram_webhooks"
REMOVE_HANDLER_URL = ""


async def async_setup_platform(hass, config):
    """Set up the Telegram webhooks platform."""

    bot = initialize_bot(config)

    current_status = await hass.async_add_job(bot.getWebhookInfo)
    base_url = config.get(
        CONF_URL, get_url(hass, require_ssl=True, allow_internal=False)
    )

    # Some logging of Bot current status:
    last_error_date = getattr(current_status, "last_error_date", None)
    if (last_error_date is not None) and (isinstance(last_error_date, int)):
        last_error_date = dt.datetime.fromtimestamp(last_error_date)
        _LOGGER.info(
            "telegram webhook last_error_date: %s. Status: %s",
            last_error_date,
            current_status,
        )
    else:
        _LOGGER.debug("telegram webhook Status: %s", current_status)

    handler_url = f"{base_url}{TELEGRAM_HANDLER_URL}"
    if not handler_url.startswith("https"):
        _LOGGER.error("Invalid telegram webhook %s must be https", handler_url)
        return False

    def _try_to_set_webhook():
        retry_num = 0
        while retry_num < 3:
            try:
                return bot.setWebhook(handler_url, timeout=5)
            except TimedOut:
                retry_num += 1
                _LOGGER.warning("Timeout trying to set webhook (retry #%d)", retry_num)

    if current_status and current_status["url"] != handler_url:
        result = await hass.async_add_job(_try_to_set_webhook)
        if result:
            _LOGGER.info("Set new telegram webhook %s", handler_url)
        else:
            _LOGGER.error("Set telegram webhook failed %s", handler_url)
            return False

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, lambda event: bot.setWebhook(REMOVE_HANDLER_URL)
    )
    hass.http.register_view(
        BotPushReceiver(
            hass, config[CONF_ALLOWED_CHAT_IDS], config[CONF_TRUSTED_NETWORKS]
        )
    )
    return True


class BotPushReceiver(HomeAssistantView, BaseTelegramBotEntity):
    """Handle pushes from Telegram."""

    requires_auth = False
    url = TELEGRAM_HANDLER_URL
    name = "telegram_webhooks"

    def __init__(self, hass, allowed_chat_ids, trusted_networks):
        """Initialize the class."""
        BaseTelegramBotEntity.__init__(self, hass, allowed_chat_ids)
        self.trusted_networks = trusted_networks

    async def post(self, request):
        """Accept the POST from telegram."""
        real_ip = ip_address(request.remote)
        if not any(real_ip in net for net in self.trusted_networks):
            _LOGGER.warning("Access denied from %s", real_ip)
            return self.json_message("Access denied", HTTP_UNAUTHORIZED)

        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)

        if not self.process_message(data):
            return self.json_message("Invalid message", HTTP_BAD_REQUEST)
        return None
