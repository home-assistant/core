"""Config flow for Linear Garage Door integration."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
import logging
from typing import Any
import uuid

from linear_garage_door import Linear
from linear_garage_door.errors import InvalidLoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = {
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
}


async def validate_input(
    hass: HomeAssistant,
    data: dict[str, str],
) -> dict[str, Sequence[Collection[str]]]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = Linear()

    device_id = str(uuid.uuid4())
    try:
        await hub.login(
            data["email"],
            data["password"],
            device_id=device_id,
            client_session=async_get_clientsession(hass),
        )

        sites = await hub.get_sites()
    except InvalidLoginError as err:
        raise InvalidAuth from err
    finally:
        await hub.close()

    return {
        "email": data["email"],
        "password": data["password"],
        "sites": sites,
        "device_id": device_id,
    }


class LinearGarageDoorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Linear Garage Door."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Sequence[Collection[str]]] = {}
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(STEP_USER_DATA_SCHEMA)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.data = info

            # Check if we are reauthenticating
            if self._reauth_entry is not None:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=self._reauth_entry.data
                    | {"email": self.data["email"], "password": self.data["password"]},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return await self.async_step_site()

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_site(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the site step."""

        if isinstance(self.data["sites"], list):
            sites: list[dict[str, str]] = self.data["sites"]

        if not user_input:
            return self.async_show_form(
                step_id="site",
                data_schema=vol.Schema(
                    {
                        vol.Required("site"): vol.In(
                            {site["id"]: site["name"] for site in sites}
                        )
                    }
                ),
            )

        site_id = user_input["site"]

        site_name = next(site["name"] for site in sites if site["id"] == site_id)

        await self.async_set_unique_id(site_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=site_name,
            data={
                "site_id": site_id,
                "email": self.data["email"],
                "password": self.data["password"],
                "device_id": self.data["device_id"],
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth in case of a password change or other error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidDeviceID(HomeAssistantError):
    """Error to indicate there is invalid device ID."""
