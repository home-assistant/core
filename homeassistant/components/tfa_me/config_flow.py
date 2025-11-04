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

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.name_with_station_id: bool = False

    _LOGGER.debug("TFA.me config flow")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: Configuration UI."""
        errors: dict[str, str] = {}

        # No input (empty)
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        # Get multiple entities option
        multi_ent = user_input.get(CONF_NAME_WITH_STATION_ID)
        if not isinstance(multi_ent, bool):
            self.name_with_station_id = False
            errors[CONF_NAME_WITH_STATION_ID] = "invalid_name_with_station_id"
            # Error, multiple entities validation failed
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )
        self.name_with_station_id = multi_ent

        # Get IP or mDNS host name
        ip_host_str = user_input.get(CONF_IP_ADDRESS)

        # If user_input is not None:
        validator = TFAmeValidator()
        if validator.is_valid_ip_or_tfa_me(ip_host_str):
            title_str: str = DEFAULT_STATION_NAME
            if isinstance(ip_host_str, str):
                title_str = DEFAULT_STATION_NAME + " '" + ip_host_str.upper() + "'"

            try:
                client = TFAmeData(user_input[CONF_IP_ADDRESS])
                identifier = await client.get_identifier()
            except TFAmeException:
                errors["base"] = "host_empty"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()

                # Create a TFA.me device entry
                return self.async_create_entry(title=title_str, data=user_input)

        # Update error list: invalid IP or host
        errors[CONF_IP_ADDRESS] = "invalid_ip_host"

        # Error, validation failed
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
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
                await coordinator.async_refresh()
                # Update all entities on dashboard
                cordy: TFAmeDataCoordinator = coordinator
                for entity in cordy.sensor_entity_list:
                    if "_rain_" in entity:
                        coordinator.data[entity]["reset_rain"] = True
                        msg_reset = f"{entity} rain reset"
                        _LOGGER.info(msg_reset)
                        await self.hass.services.async_call(
                            "homeassistant", "update_entity", {"entity_id": entity}
                        )

                return self.async_create_entry(
                    title="action_rain", data=self.config_entry.options
                )

        action_schema_rain = vol.Schema({vol.Required("action_rain"): vol.Boolean()})
        return self.async_show_form(
            step_id="action_rain",
            data_schema=action_schema_rain,
        )
