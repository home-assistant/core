"""Constants for the Cookidoo integration."""

from typing import Final

from homeassistant.const import CONF_HOST, CONF_PORT

DOMAIN = "cookidoo"

BROWSER_RUNNER_CHECK_DEFAULT = [
    {CONF_HOST: "homeassistant.local", CONF_PORT: "9222"},
    {CONF_HOST: "localhost", CONF_PORT: "9222"},
    {CONF_HOST: "5afecb1b-chromium-runner", CONF_PORT: "9222"},
    {CONF_HOST: "5afecb1b-chromium", CONF_PORT: "9222"},
]
BROWSER_RUNNER_TIMEOUT: Final = 20000  # s

TODO_ITEMS: Final = "items"
TODO_ADDITIONAL_ITEMS: Final = "additional_items"
