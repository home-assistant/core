"""Config flow for the openSenseMap integration."""

from typing import Any

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID, DOMAIN, ERROR_CANNOT_CONNECT, ERROR_INVALID_STATION


class CannotConnect(HomeAssistantError):
    """Error to indicate the openSenseMap API is unreachable."""


class InvalidStation(HomeAssistantError):
    """Error to indicate the station ID does not exist."""


class OpenSenseMapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for openSenseMap."""

    VERSION = 1

    async def _async_get_station_name(self, station_id: str) -> str:
        """Validate the station ID and return its name."""
        session = async_get_clientsession(self.hass)
        api = OpenSenseMap(station_id, session)
        try:
            # opensensemap_api wraps the request in a 5s aiohttp.ClientTimeout
            # and re-raises asyncio.TimeoutError as OpenSenseMapConnectionError.
            await api.get_data()
        except OpenSenseMapError as err:
            raise CannotConnect from err
        if not api.data or not api.data.get("name"):
            raise InvalidStation
        return api.data["name"]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            try:
                name = await self._async_get_station_name(station_id)
            except CannotConnect:
                errors["base"] = ERROR_CANNOT_CONNECT
            except InvalidStation:
                errors["base"] = ERROR_INVALID_STATION
            else:
                await self.async_set_unique_id(station_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={CONF_STATION_ID: station_id},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_STATION_ID): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import of a YAML configuration."""
        station_id = import_data[CONF_STATION_ID]
        await self.async_set_unique_id(station_id)
        self._abort_if_unique_id_configured()

        # Even when YAML provides a display name, validate the station before
        # migrating so broken YAML does not create an entry that cannot set up.
        try:
            name = await self._async_get_station_name(station_id)
        except CannotConnect:
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)
        except InvalidStation:
            return self.async_abort(reason=ERROR_INVALID_STATION)

        return self.async_create_entry(
            title=import_data.get(CONF_NAME) or name,
            data={CONF_STATION_ID: station_id},
        )
