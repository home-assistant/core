"""Config flow for sky_remote."""

import logging
from typing import Any

from skyboxremote import RemoteControl, SkyBoxConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DOMAIN, LEGACY_PORT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


async def async_find_box_port(host: str) -> int:
    """Find port box uses for communication."""
    _LOGGER.debug("Attempting to find port to connect to %s on", host)
    remote = RemoteControl(host, DEFAULT_PORT)
    try:
        await remote.check_connectable()
    except SkyBoxConnectionError:
        # Try legacy port if the default one failed
        remote = RemoteControl(host, LEGACY_PORT)
        await remote.check_connectable()
        return LEGACY_PORT
    return DEFAULT_PORT


class SkyRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sky Remote."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug("user_input: %s", user_input)
            self._async_abort_entries_match(user_input)
            try:
                port = await async_find_box_port(user_input[CONF_HOST])
            except SkyBoxConnectionError:
                _LOGGER.exception("While finding port of skybox")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data={**user_input, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
