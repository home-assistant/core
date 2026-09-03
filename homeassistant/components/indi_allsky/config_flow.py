"""Config flow for INDI Allsky integration."""

import logging
from typing import Any, override

from aioindiallsky import (
    IndiAllSkyAuthError,
    IndiAllSkyClient,
    IndiAllSkyConnectionError,
    IndiAllSkyTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN
from .util import get_ssl_context

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="host",
            ),
        ),
        vol.Required(CONF_PORT, default=443): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=65535,
                mode=NumberSelectorMode.BOX,
            ),
        ),
        vol.Optional(CONF_SSL, default=True): BooleanSelector(),
        vol.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate that the user input allows us to connect to INDI Allsky."""
    client = IndiAllSkyClient(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        ssl=get_ssl_context(
            data.get(CONF_SSL, True),
            data.get(CONF_VERIFY_SSL, True),
        ),
        session=async_get_clientsession(hass),
    )

    try:
        await client.fetch_image("latestimage")
        await client.connect()
    except IndiAllSkyAuthError as err:
        _LOGGER.error(
            "Authentication failed for INDI Allsky at %s:%s: %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise InvalidAuth from err
    except (IndiAllSkyConnectionError, IndiAllSkyTimeoutError) as err:
        _LOGGER.error(
            "Cannot connect to INDI Allsky instance at %s:%s: %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise CannotConnect from err
    except Exception as err:
        raise Unknown from err
    finally:
        await client.disconnect()


class IndiAllSkyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for INDI Allsky."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                port = user_input[CONF_PORT]
                default_port = 443 if user_input.get(CONF_SSL, True) else 80
                host_str = (
                    f"{user_input[CONF_HOST]}:{port}"
                    if port != default_port
                    else user_input[CONF_HOST]
                )
                return self.async_create_entry(
                    title=f"INDI Allsky ({host_str})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class Unknown(HomeAssistantError):
    """Unexpected error."""
