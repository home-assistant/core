"""TFA.me station integration: config_flow.py."""

import logging
from typing import Any

from tfa_me_ha_local.validators import TFAmeValidator
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_NAME_WITH_STATION_ID, DEFAULT_STATION_NAME, DOMAIN
from .coordinator import TFAmeDataCoordinator
from .data import TFAmeData, TFAmeException

# Scheme for IP/Domain and poll interval
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_NAME_WITH_STATION_ID): bool,
    }
)


_LOGGER = logging.getLogger(__name__)


class TFAmeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for TFA.me stations."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.name_with_station_id: bool = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate "name_with_station_id" option
            add_station_id = user_input.get(CONF_NAME_WITH_STATION_ID)
            if not isinstance(add_station_id, bool):
                self.name_with_station_id = False
                errors[CONF_NAME_WITH_STATION_ID] = "invalid_name_with_station_id"
            else:
                self.name_with_station_id = add_station_id

            # Validate the host (IP or mDNS hostname)
            ip_host_str = user_input.get(CONF_IP_ADDRESS)
            validator = TFAmeValidator()

            # Only validate host if no previous errors exist
            if not errors and validator.is_valid_ip_or_tfa_me(ip_host_str):
                title_str: str = DEFAULT_STATION_NAME
                if isinstance(ip_host_str, str):
                    title_str = f"{DEFAULT_STATION_NAME} '{ip_host_str.upper()}'"

                try:
                    data_helper: TFAmeData = TFAmeData(self.hass, str(ip_host_str))
                    identifier = await data_helper.get_identifier()

                except TFAmeException:
                    # Device responded or connection was attempted but failed
                    errors["base"] = "host_empty"

                except Exception:
                    # Any unexpected exception should be logged and shown generically
                    _LOGGER.exception(
                        "Unexpected exception while validating TFA.me host"
                    )
                    errors["base"] = "unknown"

                else:
                    # Unique ID is the station identifier
                    await self.async_set_unique_id(identifier)
                    self._abort_if_unique_id_configured()

                    # Successfully validated → create a config entry
                    return self.async_create_entry(title=title_str, data=user_input)

            elif not errors:
                # Host is not valid at all
                errors[CONF_IP_ADDRESS] = "invalid_ip_host"

        # When user_input is None (first load) or when errors occurred,
        # the flow must show the form again with error messages.
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Options flow handler (reset rain, etc.) for TFA.me integration."""

    async def async_step_init(self, user_input: None) -> ConfigFlowResult:
        """Handle options menu flow."""

        # Is an option selected?
        if user_input is not None:
            if "select_option" in user_input:
                if user_input["select_option"] == "action_rain":
                    return await self.async_step_action_rain(user_input)

        # No option seletced -> build main option menu
        opt_dict = [
            SelectOptionDict(value="none", label="None"),
            SelectOptionDict(value="action_rain", label="Reset all rain sensors"),
        ]

        options_schema = vol.Schema(
            {
                vol.Required(
                    "select_option", default="none", description="Select a option:"
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=opt_dict,
                        mode=SelectSelectorMode.DROPDOWN,  # Dropdown-Menu
                    )
                )
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)

    async def async_step_action_rain(self, user_input=None) -> ConfigFlowResult:
        """Entry point for option: Reset all rain sensors."""
        if user_input is not None:
            if user_input["select_option"] == "action_rain":
                coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
                # Store in options
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, "action_rain": True},
                )
                # Update all entities on dashboard
                cordy: TFAmeDataCoordinator = coordinator
                for entity in cordy.sensor_entity_list:
                    if "_rain_" in entity:
                        coordinator.data[entity]["reset_rain"] = True
                        msg_reset = f"{entity} rain reset"
                        _LOGGER.info(msg_reset)

                # Update UI
                coordinator.async_set_updated_data(coordinator.data)

                return self.async_create_entry(
                    title="action_rain", data=self.config_entry.options
                )

        action_schema_rain = vol.Schema({vol.Required("action_rain"): vol.Boolean()})
        return self.async_show_form(
            step_id="action_rain",
            data_schema=action_schema_rain,
        )
