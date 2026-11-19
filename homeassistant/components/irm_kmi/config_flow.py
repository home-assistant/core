"""Config flow to set up IRM KMI integration via the UI."""

import logging
from typing import Any, override

from irm_kmi_api import IrmKmiApiClient, IrmKmiApiError
import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LANGUAGE_OVERRIDE,
    CONF_LANGUAGE_OVERRIDE_OPTIONS,
    DOMAIN,
    OUT_OF_BENELUX,
    USER_AGENT,
)
from .coordinator import IrmKmiConfigEntry

_LOGGER = logging.getLogger(__name__)


class IrmKmiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for the IRM KMI integration."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(_config_entry: IrmKmiConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return IrmKmiOptionFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self._async_step_location(
            "user",
            user_input,
            {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the location."""
        return await self._async_step_location(
            "reconfigure",
            user_input,
            self._get_reconfigure_entry().data[CONF_LOCATION],
        )

    async def _async_step_location(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        location: dict[str, float],
    ) -> ConfigFlowResult:
        """Validate a location and create or update the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            try:
                api_data = await IrmKmiApiClient(
                    session=async_get_clientsession(self.hass),
                    user_agent=USER_AGENT,
                ).get_forecasts_coord(
                    {
                        "lat": location[CONF_LATITUDE],
                        "long": location[CONF_LONGITUDE],
                    }
                )
            except IrmKmiApiError:
                errors["base"] = "cannot_connect"
            else:
                if api_data["cityName"] in OUT_OF_BENELUX:
                    errors[CONF_LOCATION] = "out_of_benelux"
                else:
                    name: str = api_data["cityName"]
                    unique_id = f"{name.lower()} {api_data['country'].lower()}"
                    await self.async_set_unique_id(unique_id)
                    if self.source == SOURCE_RECONFIGURE:
                        return await self._async_move_entry(name, unique_id, location)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={CONF_LOCATION: location, CONF_UNIQUE_ID: unique_id},
                    )

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {probatio.Required(CONF_LOCATION, default=location): LocationSelector()}
            ),
            errors=errors,
        )

    async def _async_move_entry(
        self, name: str, unique_id: str, location: dict[str, float]
    ) -> ConfigFlowResult:
        """Move the entry to a new location, keeping its entities."""
        entry = self._get_reconfigure_entry()
        title = entry.title
        if unique_id != entry.unique_id:
            self._abort_if_unique_id_configured()
            old_unique_id = entry.data[CONF_UNIQUE_ID]

            @callback
            def _new_unique_id(entity: er.RegistryEntry) -> dict[str, str]:
                return {
                    "new_unique_id": unique_id
                    + entity.unique_id.removeprefix(old_unique_id)
                }

            await er.async_migrate_entries(self.hass, entry.entry_id, _new_unique_id)
            # Keep a title the user renamed
            if title.lower() == old_unique_id.rsplit(" ", 1)[0]:
                title = name
        return self.async_update_reload_and_abort(
            entry,
            unique_id=unique_id,
            title=title,
            data_updates={CONF_LOCATION: location, CONF_UNIQUE_ID: unique_id},
        )


class IrmKmiOptionFlow(OptionsFlowWithReload):
    """Option flow for the IRM KMI integration.

    Helps change options once the integration was configured.
    """

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("Provided config user is: %s", user_input)
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_LANGUAGE_OVERRIDE,
                        default=self.config_entry.options.get(
                            CONF_LANGUAGE_OVERRIDE, "none"
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=CONF_LANGUAGE_OVERRIDE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_LANGUAGE_OVERRIDE,
                        )
                    )
                }
            ),
        )
