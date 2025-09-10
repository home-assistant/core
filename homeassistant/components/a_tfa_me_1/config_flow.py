"""TFA.me station integration: config_flow.py."""

import logging
import re
from typing import Any

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

from .const import CONF_INTERVAL, CONF_MULTIPLE_ENTITIES, DOMAIN
from .coordinator import TFAmeDataCoordinator
from .data import TFAmeData, TFAmeException

# Scheme for IP/Domain and poll interval
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_INTERVAL, default=60): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=3600)
        ),  # Interval between 10 and 3600 seconds
        vol.Required(CONF_MULTIPLE_ENTITIES): bool,
    }
)


_LOGGER = logging.getLogger(__name__)


# ---- TFA.me config flow ----
class TFAmeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for TFA.me stations."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.multiple_entities: bool = False

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
        multi_ent = user_input.get(CONF_MULTIPLE_ENTITIES)
        if not isinstance(multi_ent, bool):
            self.multiple_entities = False
            errors[CONF_MULTIPLE_ENTITIES] = "invalid_multiple_entities"
            # Error, multiple entities validation failed
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )
        self.multiple_entities = multi_ent

        # Get interval and IP or mDNS host name
        update_interval = user_input.get(CONF_INTERVAL)
        if not isinstance(update_interval, int):
            _LOGGER.debug("update_interval no Integer, set to default")
            update_interval = 60
            errors[CONF_INTERVAL] = "invalid_interval"
            # Error, interval validation failed
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        ip_host_str = user_input.get("ip_address")

        # Verify interval
        if update_interval <= 9:
            errors[CONF_INTERVAL] = "invalid_interval"
            # Error, interval validation failed
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        # if user_input is not None:
        if is_valid_ip_or_tfa_me(user_input):
            title_str: str = "TFA.me Station"
            if isinstance(ip_host_str, str):
                title_str = "TFA.me Station '" + ip_host_str.upper() + "'"

            try:
                client = TFAmeData(user_input[CONF_IP_ADDRESS])
                identifier = await client.get_identifier()
            except TFAmeException as error:
                errors["base"] = str(error)  #  "host_empty"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()

                # Create a TFA.me device entry
                return self.async_create_entry(title=title_str, data=user_input)

        # error
        errors[CONF_IP_ADDRESS] = "invalid_ip_host"

        # Error, validation failed
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    # async def _reload_sensors(self):
    #    """Reload the sensors."""
    #    hass: HomeAssistant = self.config_entry.hass
    #    await hass.config_entries.async_reload(self.config_entry.entry_id)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


# ---- Verify if user input is valid IP V4 or valid TFA.me station ----
def is_valid_ip_or_tfa_me(to_verify: dict) -> bool:
    """Verify if input is an IP or a valid mDNS host name."""

    host = to_verify.get("ip_address")  # Get value as string
    if not isinstance(host, str):
        return False  # ip_address not available or not a string

    # IPv4 verify:
    # ipv4_pattern: str = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    ipv4_pattern = (
        r"^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}"
        r"(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$"
    )
    if re.match(ipv4_pattern, host):
        return True

    # Special format for mDNS name verification: "tfa-me-XXX-XXX-XXX.local"
    # mdns_pattern: str = r"^tfa-me-[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}\.local$"
    # Special format for mDNS name verification: "XXX-XXX-XXX"
    mdns_pattern: str = r"^[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}$"
    if re.match(mdns_pattern, host):
        return True

    return False


# ---- Options handler: set poll interval ----
class OptionsFlowHandler(OptionsFlow):
    """Options flow for for TFA.me integration."""

    async def async_step_init(self, user_input: None) -> ConfigFlowResult:
        """Handle options menu flow."""

        # Is an option selected?
        if user_input is not None:
            if "interval" in user_input:
                return await self.async_step_set_interval(user_input)

            if "select_option" in user_input:
                if user_input["select_option"] == "menu_interval":
                    return await self.async_step_set_interval(user_input)
                if user_input["select_option"] == "discover_sensors":
                    return await self.async_discover_sensors(user_input)
                if user_input["select_option"] == "action_rain":
                    return await self.async_step_action_rain(user_input)
                if user_input["select_option"] == "update_data":
                    return await self.async_update_data(user_input)

        # No option seletced -> build main option menu
        opt_dict = [
            SelectOptionDict(value="none", label="None"),
            SelectOptionDict(value="menu_interval", label="Change request interval"),
            SelectOptionDict(value="discover_sensors", label="Discover new sensors"),
            SelectOptionDict(value="action_rain", label="Reset all rain sensors"),
            SelectOptionDict(value="update_data", label="Reload sensor data"),
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

    # ---- Change option: poll interval ----
    async def async_step_set_interval(self, user_input=None) -> ConfigFlowResult:
        """Entry point for options: change request interval."""

        if user_input is not None:
            if "interval" in user_input:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Settings saved",
                        "message": f"The request/pull interval was set to {user_input['interval']} seconds.",
                        "notification_id": "options_saved",
                    },
                )
                return self.async_create_entry(title="", data=user_input)

        # Get actual values from entry
        interval = self.config_entry.data.get("interval")
        current_interval = self.config_entry.options.get(CONF_INTERVAL, interval)

        # Build options schema with interval range (10 to 3600)
        options_schema = vol.Schema(
            {
                vol.Required(CONF_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=10, max=3600),
                )
            }
        )
        # Show the form
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "interval": str(self.config_entry.options.get("interval", 10))
            },
        )

    # ---- Change option: Reset all rain sensors ----
    async def async_step_action_rain(self, user_input=None) -> ConfigFlowResult:
        """Entry point for option: Reset all rain sensors."""
        if user_input is not None:  # Remove?
            if user_input["select_option"] == "action_rain":  #  remove?
                coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
                coordinator.reset_rain_sensors = True
                # Store in options
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, "action_rain": True},
                )
                await coordinator.async_refresh()
                # Update all entities on dashboard
                cordy: TFAmeDataCoordinator = coordinator
                for number in range(1, len(cordy.sensor_entity_list)):
                    entity = coordinator.sensor_entity_list[number]
                    msg_reset = f"{entity} reset"
                    _LOGGER.info(msg_reset)
                    await self.hass.services.async_call(
                        "homeassistant", "update_entity", {"entity_id": entity}
                    )

                return self.async_create_entry(
                    title="action_rain", data=self.config_entry.options
                )
        # Remove ?
        action_schema_rain = vol.Schema({vol.Required("action_rain"): vol.Boolean()})
        return self.async_show_form(
            step_id="action_rain",
            data_schema=action_schema_rain,
        )

    # ---- Change option: Reload all sensor data ----
    async def async_update_data(self, user_input=None) -> ConfigFlowResult:
        """Entry point for option: Reload all sensor data."""
        if user_input is not None:
            if user_input["select_option"] == "update_data":
                coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
                await coordinator.async_refresh()  # get sensor data

                # Update all entities on dashboard
                for entity_id in coordinator.sensor_entity_list:
                    ent_str = str(entity_id)
                    await self.hass.services.async_call(
                        "homeassistant",
                        "update_entity",
                        {"entity_id": ent_str},
                    )

        return self.async_create_entry(
            title="update_data", data=self.config_entry.options
        )

    # ---- Change option: Discover new sensors ----
    async def async_discover_sensors(self, user_input=None) -> ConfigFlowResult:
        """Entry point for option: Discover new sensors."""
        if user_input is not None:
            if user_input["select_option"] == "discover_sensors":
                coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
                await coordinator.async_refresh()
                await coordinator.async_discover_new_entities()

        return self.async_create_entry(
            title="discover_sensors", data=self.config_entry.options
        )

    # async def _save_device_list(self, device_list):
    #    """Save list will all TFA.me stations."""
    #    self.hass.config_entries.async_update_entry(
    #        self.config_entry, data={"tfa_me_stations": device_list}
    #    )

    # def _load_device_list(self):
    #    """Load list with all TFA.me stations."""
    #    return self.config_entry.data.get("tfa_me_stations", [])
