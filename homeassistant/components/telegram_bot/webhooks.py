"""Support for Telegram bots using webhooks."""

import datetime as dt
from http import HTTPStatus
from ipaddress import ip_address
import logging
import secrets
import string

from telegram import Update
from telegram.error import TimedOut
from telegram.ext import Application, TypeHandler

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.network import get_url

from . import CONF_TRUSTED_NETWORKS, CONF_URL, BaseTelegramBotEntity

_LOGGER = logging.getLogger(__name__)

TELEGRAM_WEBHOOK_URL = "/api/telegram_webhooks"
REMOVE_WEBHOOK_URL = ""
SECRET_TOKEN_LENGTH = 32


async def async_setup_platform(hass, bot, config):
    """Set up the Telegram webhooks platform."""

    # Generate an ephemeral secret token
    alphabet = string.ascii_letters + string.digits + "-_"
    secret_token = "".join(secrets.choice(alphabet) for _ in range(SECRET_TOKEN_LENGTH))

    pushbot = PushBot(hass, bot, config, secret_token)

    if not pushbot.webhook_url.startswith("https"):
        _LOGGER.error("Invalid telegram webhook %s must be https", pushbot.webhook_url)
        return False

    await pushbot.start_application()
    webhook_registered = await pushbot.register_webhook()
    if not webhook_registered:
        return False

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pushbot.stop_application)
    hass.http.register_view(
        PushBotView(
            hass,
            bot,
            pushbot.application,
            config[CONF_TRUSTED_NETWORKS],
            secret_token,
        )
    )
    return True


class PushBot(BaseTelegramBotEntity):
    """Handles all the push/webhook logic and passes telegram updates to `self.handle_update`."""

    def __init__(self, hass, bot, config, secret_token):
        """Create Application before calling super()."""
        self.bot = bot
        self.trusted_networks = config[CONF_TRUSTED_NETWORKS]
        self.secret_token = secret_token
        # Dumb Application that just gets our updates to our handler callback (self.handle_update)
        self.application = Application.builder().bot(bot).updater(None).build()
        self.application.add_handler(TypeHandler(Update, self.handle_update))
        super().__init__(hass, config)

        self.base_url = config.get(CONF_URL) or get_url(
            hass, require_ssl=True, allow_internal=False
        )
        self.webhook_url = f"{self.base_url}{TELEGRAM_WEBHOOK_URL}"

    async def _try_to_set_webhook(self):
        _LOGGER.debug("Registering webhook URL: %s", self.webhook_url)
        retry_num = 0
        while retry_num < 3:
            try:
                return await self.bot.set_webhook(
                    self.webhook_url,
                    api_kwargs={"secret_token": self.secret_token},
                    connect_timeout=5,
                )
            except TimedOut:
                retry_num += 1
                _LOGGER.warning("Timeout trying to set webhook (retry #%d)", retry_num)

        return False

    async def start_application(self):
        """Handle starting the Application object."""
        await self.application.initialize()
        await self.application.start()

    async def register_webhook(self):
        """Query telegram and register the URL for our webhook."""
        current_status = await self.bot.get_webhook_info()
        # Some logging of Bot current status:
        last_error_date = getattr(current_status, "last_error_date", None)
        if (last_error_date is not None) and (isinstance(last_error_date, int)):
            last_error_date = dt.datetime.fromtimestamp(last_error_date)
            _LOGGER.debug(
                "Telegram webhook last_error_date: %s. Status: %s",
                last_error_date,
                current_status,
            )
        else:
            _LOGGER.debug("telegram webhook status: %s", current_status)

        if current_status and current_status["url"] != self.webhook_url:
            result = await self._try_to_set_webhook()
            if result:
                _LOGGER.info("Set new telegram webhook %s", self.webhook_url)
            else:
                _LOGGER.error("Set telegram webhook failed %s", self.webhook_url)
                return False

        return True

    async def stop_application(self, event=None):
        """Handle gracefully stopping the Application object."""
        await self.deregister_webhook()
        await self.application.stop()
        await self.application.shutdown()

    async def deregister_webhook(self):
        """Query telegram and deregister the URL for our webhook."""
        _LOGGER.debug("Deregistering webhook URL")
        await self.bot.delete_webhook()


class PushBotView(HomeAssistantView):
    """View for handling webhook calls from Telegram."""

    requires_auth = False
    url = TELEGRAM_WEBHOOK_URL
    name = "telegram_webhooks"

    def __init__(self, hass, bot, application, trusted_networks, secret_token):
        """Initialize by storing stuff needed for setting up our webhook endpoint."""
        self.hass = hass
        self.bot = bot
        self.application = application
        self.trusted_networks = trusted_networks
        self.secret_token = secret_token

    async def post(self, request):
        """Accept the POST from telegram."""
        real_ip = ip_address(request.remote)
        if not any(real_ip in net for net in self.trusted_networks):
            _LOGGER.warning("Access denied from %s", real_ip)
            return self.json_message("Access denied", HTTPStatus.UNAUTHORIZED)
        secret_token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_token_header is None or self.secret_token != secret_token_header:
            _LOGGER.warning("Invalid secret token from %s", real_ip)
            return self.json_message("Access denied", HTTPStatus.UNAUTHORIZED)

        try:
            update_data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        update = Update.de_json(update_data, self.bot)
        _LOGGER.debug("Received Update on %s: %s", self.url, update)
        await self.application.process_update(update)

        return None
