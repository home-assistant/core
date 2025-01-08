"""Config flow for Velux integration."""

from typing import Any

from pyvlx import PyVLX, PyVLXException
import voluptuous as vol

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class VeluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for velux."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovery_schema: vol.Schema | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            pyvlx = PyVLX(
                host=user_input[CONF_HOST], password=user_input[CONF_PASSWORD]
            )
            try:
                await pyvlx.connect()
                await pyvlx.disconnect()
            except (PyVLXException, ConnectionError) as err:
                errors["base"] = "cannot_connect"
                LOGGER.debug("Cannot connect: %s", err)
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME] or user_input[CONF_HOST],
                    data=user_input,
                )

        data_schema = self.discovery_schema or self.add_suggested_values_to_schema(
            DATA_SCHEMA, user_input
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery by DHCP."""
        return await self._async_handle_discovery(
            {
                CONF_HOST: discovery_info.ip,
                CONF_MAC: format_mac(discovery_info.macaddress),
                CONF_NAME: discovery_info.hostname.upper().replace("LAN_", ""),
            }
        )

    async def _async_handle_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered Velux device."""
        # The hostname ends with the last 4 digits of the device MAC address.
        await self.async_set_unique_id(discovery_info[CONF_NAME])

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info[CONF_HOST]}
        )

        # Check if config_entry already exists without unigue_id configured.
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data[CONF_HOST] == discovery_info[CONF_HOST]
                and entry.unique_id is None
            ):
                self.hass.config_entries.async_update_entry(
                    entry=entry, unique_id=discovery_info[CONF_NAME]
                )
                return self.async_abort(reason="already_configured")

        self.discovery_schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA, discovery_info
        )
        return await self.async_step_user()
