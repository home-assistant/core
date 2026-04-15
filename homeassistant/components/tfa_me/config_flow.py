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
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_NAME_WITH_STATION_ID, DEFAULT_STATION_NAME, DOMAIN, RAIN_KEYS
from .coordinator import TFAmeUpdateCoordinator
from .data import TFAmeException, TFAmeUniqueID

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

        # For zeroconf discovery
        self._discovered_host_or_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}

        default_host = self._discovered_host_or_id or ""
        default_name_with_id = False

        data_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS, default=default_host): str,
                vol.Required(
                    CONF_NAME_WITH_STATION_ID, default=default_name_with_id
                ): bool,
            }
        )

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
                    data_helper: TFAmeUniqueID = TFAmeUniqueID(
                        self.hass, str(ip_host_str)
                    )
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
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Discover TFA.me stations via mDNS (zeroconf) service '_tfa_me._tcp'."""
        props = discovery_info.properties or {}
        unique_id = (props.get("id") or "").strip()
        host = (discovery_info.host or "").rstrip(".")

        # Add "Discovered" info
        self.context["configuration_url"] = f"http://{host}/ha_menu"
        self._discovered_host_or_id = host or None
        if unique_id:
            formatted_station_id = f"{unique_id[:3].upper()}-{unique_id[3:6].upper()}-{unique_id[6:].upper()}"
            title = f"{DEFAULT_STATION_NAME} {formatted_station_id}"  # e.g. "TFA.me Station XXX-XXX-XXX"
            self.context["title_placeholders"] = {
                "name": title,
                "id": unique_id,
            }
            self._discovered_host_or_id = f"{host or None} or {formatted_station_id}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        # Show "Discovered" -> user must confirm (ADD)
        return await self.async_step_user()


class OptionsFlowHandler(OptionsFlow):
    """Options flow handler for TFA.me integration."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Handle options menu flow."""

        if user_input is not None:
            if user_input.get("action_rain"):
                coordinator = self.config_entry.runtime_data

                # Store in options
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, "action_rain": True},
                )

                # Set rain reset marker and update all entities on dashboard
                cordy: TFAmeUpdateCoordinator = coordinator
                for entity in cordy.sensor_entity_list:
                    if any(k in entity for k in RAIN_KEYS):
                        coordinator.data.entities[entity]["reset_rain"] = True
                        msg_reset = f"{entity} rain reset"
                        _LOGGER.info(msg_reset)

                coordinator.async_set_updated_data(coordinator.data)

            # Options flow must always finish with create_entry
            return self.async_create_entry(title="", data=self.config_entry.options)

        schema = vol.Schema(
            {
                vol.Optional(
                    "action_rain",
                    default=False,
                    description="Reset all rain sensors",
                ): bool
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
