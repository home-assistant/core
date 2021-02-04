"""Config flow for Elk-M1 Control integration."""
import asyncio
import logging
from urllib.parse import urlparse

import elkm1_lib as elkm1
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PROTOCOL,
    CONF_TEMPERATURE_UNIT,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util import slugify

from . import async_wait_for_elk_to_sync
from .const import CONF_AUTO_CONFIGURE, CONF_PREFIX
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

PROTOCOL_MAP = {"secure": "elks://", "non-secure": "elk://", "serial": "serial://"}

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PROTOCOL, default="secure"): vol.In(
            ["secure", "non-secure", "serial"]
        ),
        vol.Required(CONF_ADDRESS): str,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_PREFIX, default=""): str,
        vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_FAHRENHEIT): vol.In(
            [TEMP_FAHRENHEIT, TEMP_CELSIUS]
        ),
    }
)

VALIDATE_TIMEOUT = 35


async def validate_input(data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    userid = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    prefix = data[CONF_PREFIX]
    url = _make_url_from_data(data)
    requires_password = url.startswith("elks://")

    if requires_password and (not userid or not password):
        raise InvalidAuth

    elk = elkm1.Elk(
        {"url": url, "userid": userid, "password": password, "element_list": ["panel"]}
    )
    elk.connect()

    if not await async_wait_for_elk_to_sync(elk, VALIDATE_TIMEOUT, url):
        raise InvalidAuth

    device_name = data[CONF_PREFIX] if data[CONF_PREFIX] else "ElkM1"
    # Return info that you want to store in the config entry.
    return {"title": device_name, CONF_HOST: url, CONF_PREFIX: slugify(prefix)}


def _make_url_from_data(data):
    host = data.get(CONF_HOST)
    if host:
        return host

    protocol = PROTOCOL_MAP[data[CONF_PROTOCOL]]
    address = data[CONF_ADDRESS]
    return f"{protocol}{address}"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elk-M1 Control."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the elkm1 config flow."""
        self.importing = False

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if self._url_already_configured(_make_url_from_data(user_input)):
                return self.async_abort(reason="address_already_configured")

            try:
                info = await validate_input(user_input)

            except asyncio.TimeoutError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_PREFIX])
                self._abort_if_unique_id_configured()

                if self.importing:
                    return self.async_create_entry(title=info["title"], data=user_input)

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: info[CONF_HOST],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_AUTO_CONFIGURE: True,
                        CONF_TEMPERATURE_UNIT: user_input[CONF_TEMPERATURE_UNIT],
                        CONF_PREFIX: info[CONF_PREFIX],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        self.importing = True
        return await self.async_step_user(user_input)

    def _url_already_configured(self, url):
        """See if we already have a elkm1 matching user input configured."""
        existing_hosts = {
            urlparse(entry.data[CONF_HOST]).hostname
            for entry in self._async_current_entries()
        }
        return urlparse(url).hostname in existing_hosts


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
