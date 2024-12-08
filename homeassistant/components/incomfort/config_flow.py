"""Config flow support for Intergas InComfort integration."""

from typing import Any

from aiohttp import ClientResponseError
from incomfortclient import IncomfortError, InvalidHeaterList
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN
from .coordinator import async_connect_gateway

TITLE = "Intergas InComfort/Intouch Lan2RF gateway"

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="admin")
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

ERROR_STATUS_MAPPING: dict[int, tuple[str, str]] = {
    401: (CONF_PASSWORD, "auth_error"),
    404: ("base", "not_found"),
}


async def async_try_connect_gateway(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, str] | None:
    """Try to connect to the Lan2RF gateway."""
    try:
        await async_connect_gateway(hass, config)
    except InvalidHeaterList:
        return {"base": "no_heaters"}
    except IncomfortError as exc:
        if isinstance(exc.message, ClientResponseError):
            scope, error = ERROR_STATUS_MAPPING.get(
                exc.message.status, ("base", "unknown")
            )
            return {scope: error}
        return {"base": "unknown"}
    except TimeoutError:
        return {"base": "timeout_error"}
    except Exception:  # noqa: BLE001
        return {"base": "unknown"}

    return None


class InComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow to set up an Intergas InComfort boyler and thermostats."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if (
                errors := await async_try_connect_gateway(self.hass, user_input)
            ) is None:
                return self.async_create_entry(title=TITLE, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
