"""TFA.me station integration: config_flow.py."""

import logging
from typing import Any

from tfa_me_ha_local.validators import TFAmeValidator
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS

from .const import CONF_NAME_WITH_STATION_ID, DEFAULT_STATION_NAME, DOMAIN
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
