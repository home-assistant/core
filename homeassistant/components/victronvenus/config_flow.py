"""Config flow for victronvenus integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from victronvenusclient import (
    CannotConnectError,
    Hub as VictronVenusHub,
    InvalidAuthError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_SERIAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_SSL): bool,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): str}
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from zeroconf values as well as user input.

    Returns the installation id upon success.
    """

    hub = VictronVenusHub(
        data[CONF_HOST],
        data.get(CONF_PORT, DEFAULT_PORT),
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
        data.get(CONF_SSL, False),
        data.get(CONF_SERIAL, "NOSERIAL"),
    )

    return await hub.verify_connection_details()


class VictronVenusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for victronvenus."""

    def __init__(self) -> None:
        """Initialize."""
        self.hostname: str | None = None
        self.serial: str | None = None
        self.installation_id: str | None = None
        self.friendlyName: str | None = None
        self.modelName: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**user_input, CONF_SERIAL: self.serial, CONF_MODEL: self.modelName}
            data = {
                k: v for k, v in data.items() if v is not None
            }  # remove None values.

            try:
                installation_id = await validate_input(self.hass, data)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                data[CONF_INSTALLATION_ID] = installation_id
                unique_id = installation_id
                await self.async_set_unique_id(unique_id)

                self._abort_if_unique_id_configured()

                if self.friendlyName:
                    title = self.friendlyName
                else:
                    title = f"Victron OS {unique_id}"
                return self.async_create_entry(title=title, data=data)

        if user_input is None:
            default_host = self.hostname or DEFAULT_HOST
            dynamic_schema = vol.Schema(
                {
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL): bool,
                }
            )

        else:
            dynamic_schema = STEP_USER_DATA_SCHEMA

        return self.async_show_form(
            step_id="user",
            data_schema=dynamic_schema,
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle UPnP  discovery."""
        self.hostname = str(urlparse(discovery_info.ssdp_location).hostname)

        self.serial = discovery_info.upnp["serialNumber"]
        self.installation_id = discovery_info.upnp["X_VrmPortalId"]
        self.modelName = discovery_info.upnp["modelName"]
        self.friendlyName = discovery_info.upnp["friendlyName"]

        await self.async_set_unique_id(self.installation_id)
        self._abort_if_unique_id_configured()

        try:
            await validate_input(
                self.hass, {CONF_HOST: self.hostname, CONF_SERIAL: self.serial}
            )
        except InvalidAuthError:
            return await self.async_step_user()
        else:
            return self.async_create_entry(
                title=str(self.friendlyName),
                data={
                    CONF_HOST: self.hostname,
                    CONF_SERIAL: self.serial,
                    CONF_INSTALLATION_ID: self.installation_id,
                    CONF_MODEL: self.modelName,
                },
            )
