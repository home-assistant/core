"""Config flow for the Voltie Charger integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from voltie import (
    DEFAULT_PORT,
    VoltieAuthenticationError,
    VoltieCharger,
    VoltieConnectionError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER, MIN_API_VERSION

CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(autocomplete="username")
        ),
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

CONNECTION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(autocomplete="off")
        ),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
).extend(CREDENTIALS_SCHEMA.schema)


def _title(charger_id: str) -> str:
    """Return the name of a charger, from the last characters of its ID."""
    return f"Voltie Charger {charger_id[-4:].lower()}"


class VoltieChargerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Voltie Charger."""

    # Continues the numbering of the custom integration this one replaces,
    # so the entries it created load unchanged
    VERSION = 2

    async def _async_get_charger_id(
        self, data: Mapping[str, Any]
    ) -> tuple[str | None, dict[str, str]]:
        """Connect to the charger and return its ID, or the errors to show."""
        username = data.get(CONF_USERNAME) or None
        password = data.get(CONF_PASSWORD) or None
        if (username is None) != (password is None):
            return None, {"base": "incomplete_credentials"}

        charger = VoltieCharger(
            data[CONF_HOST],
            port=int(data.get(CONF_PORT, DEFAULT_PORT)),
            username=username,
            password=password,
            session=async_get_clientsession(self.hass),
            retries=0,
        )
        try:
            status = await charger.status()
            api_version = await charger.api_version()
        except VoltieAuthenticationError:
            return None, {"base": "invalid_auth"}
        except VoltieConnectionError:
            return None, {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}
        if (api_version or 0) < MIN_API_VERSION:
            return None, {"base": "unsupported_firmware"}
        return status.charger_id, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            charger_id, errors = await self._async_get_charger_id(user_input)
            if charger_id is not None:
                await self.async_set_unique_id(charger_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_title(charger_id), data=_entry_data(user_input)
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONNECTION_SCHEMA, _without_password(user_input or {})
            ),
            errors=errors,
        )


def _credentials(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return the credentials of a form, with the empty fields left out."""
    return {key: data[key] for key in (CONF_USERNAME, CONF_PASSWORD) if data.get(key)}


def _entry_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return the data to store for a charger."""
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_PORT: int(data.get(CONF_PORT, DEFAULT_PORT)),
        **_credentials(data),
    }


def _without_password(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return form values to suggest again; a password is never shown."""
    return {key: value for key, value in data.items() if key != CONF_PASSWORD}
