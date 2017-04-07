"""
Allows utilizing telegram incoming commands.

Inspired by : telegram_webhooks.py
https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/telegram_webhooks.py

Once Hass will upgrade to python version >= 3.5 an async library like
aiotg could be used for this.
https://github.com/szastupov/aiotg
"""

import logging
from threading import Thread
from time import sleep
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_START, \
    EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

EVENT_TELEGRAM_COMMAND = 'telegram.command'

ATTR_COMMAND = 'command'
ATTR_USER_ID = 'user_id'
ATTR_ARGS = 'args'
ATTR_FROM_FIRST = 'from_first'
ATTR_FROM_LAST = 'from_last'

# The domain of your component. Should be equal to the name of your component.
DOMAIN = 'telegram_poll'
BOT_TOKEN = 'bot_token'
ALLOWED_CHAT_IDS = 'allowed_chat_ids'

REQUIREMENTS = ['python-telegram-bot==5.3.0']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(BOT_TOKEN): cv.string,
        vol.Required(ALLOWED_CHAT_IDS): vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup is called when Home Assistant is loading our component."""
    import telegram
    bot_token = config[DOMAIN].get(BOT_TOKEN)
    bot = telegram.Bot(bot_token)
    return _setup(hass, config, bot)


def _setup(hass, config, bot):
    """The actual setup of the telegram component."""
    allowed_chat_ids = config[DOMAIN].get(ALLOWED_CHAT_IDS)
    checker = IncomingChecker(bot, hass, allowed_chat_ids)

    def _start_bot(_event):
        """Start the polling thread."""
        checker.check_thread.start()

    def _stop_bot(_event):
        """Stop the thread."""
        checker.checking = False

    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_START,
        _start_bot
    )
    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _stop_bot
    )

    # Return boolean to indicate that initialization was successfully.
    return True


class IncomingChecker:
    """Threaded telegram incoming message handler."""

    def __init__(self, bot, hass, allowed_ids):
        """Initialize the thread."""
        self.update_id = None
        self.bot = bot
        self.hass = hass
        # boolean to check if checking loop should continue running
        self.checking = True
        self.allowed_ids = allowed_ids
        self.check_thread = Thread(target=self.check_incoming)

    def handle(self):
        """" Receiving and processing incoming messages."""
        for update in self.bot.getUpdates(offset=self.update_id, timeout=10):
            self.update_id = update.update_id + 1

            # Updates can also be empty.
            if update.message:
                # we only want to process text messages and coming from
                # allowed ids
                chat_id = str(update.message.chat_id)
                if (update.message.text and
                        chat_id in self.allowed_ids):
                    command = update.message.text.split(' ')
                    self.hass.bus.fire(EVENT_TELEGRAM_COMMAND, {
                        ATTR_COMMAND: command[0],
                        ATTR_ARGS: ' '.join(command[1:]),
                        ATTR_FROM_FIRST: update.message.from_user.first_name,
                        ATTR_FROM_LAST: update.message.from_user.last_name,
                        ATTR_USER_ID: chat_id
                    })

    def check_incoming(self):
        """"Loop which continuously checks for incoming telegram messages."""
        # get the first pending update_id, this is so
        # we can skip over it in case
        # we get an "Unauthorized" exception.
        import telegram
        try:
            self.update_id = self.bot.getUpdates()[0].update_id
        except IndexError:
            self.update_id = None
        while self.checking:
            try:
                self.handle()
            except telegram.error.NetworkError:
                sleep(1)
            except telegram.error.Unauthorized:
                self.update_id += 1
