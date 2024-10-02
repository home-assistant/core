"""Config flow for ezbeq Profile Loader integration."""

import logging
from typing import Any

from httpx import HTTPStatusError, RequestError
from pyezbeq.consts import DEFAULT_PORT, DISCOVERY_ADDRESS
from pyezbeq.ezbeq import EzbeqClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

# User schema
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DISCOVERY_ADDRESS): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class EzBEQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ezbeq Profile Loader."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.ezbeq_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        async def test_connection() -> bool:
            """Test if we can connect to the ezbeq server."""
            client = EzbeqClient(
                host=self.ezbeq_data[CONF_HOST], port=self.ezbeq_data[CONF_PORT]
            )
            try:
                await client.get_version()
            except (HTTPStatusError, RequestError) as e:
                _LOGGER.error("Error connecting to ezbeq: %s", e)
                return False
            finally:
                await client.client.aclose()

            return True

        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        self.ezbeq_data.update(user_input)
        # abort on same info
        self._async_abort_entries_match(user_input)

        # make sure the connection is working
        if not await test_connection():
            _LOGGER.error("CannotConnect error caught")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user", errors=errors, data_schema=STEP_USER_DATA_SCHEMA
            )

        return self.async_create_entry(title=DEFAULT_NAME, data=self.ezbeq_data)
