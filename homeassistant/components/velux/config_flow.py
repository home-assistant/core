"""Config flow for Velux integration."""

from typing import Any

from pyvlx import PyVLX, PyVLXException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN, LOGGER

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def _check_connection(host: str, password: str) -> dict[str, Any]:
    """Check if we can connect to the Velux bridge."""
    pyvlx = PyVLX(host=host, password=password)
    try:
        await pyvlx.connect()
        await pyvlx.disconnect()
    except (PyVLXException, ConnectionError) as err:
        LOGGER.debug("Cannot connect: %s", err)
        return {"base": "cannot_connect"}
    except Exception as err:  # noqa: BLE001
        LOGGER.exception("Unexpected exception: %s", err)
        return {"base": "unknown"}

    return {}


class VeluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for velux."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovery_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            errors = await _check_connection(
                user_input[CONF_HOST], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery by DHCP."""
        # The hostname ends with the last 4 digits of the device MAC address.
        self.discovery_data[CONF_HOST] = discovery_info.ip
        self.discovery_data[CONF_MAC] = format_mac(discovery_info.macaddress)
        self.discovery_data[CONF_NAME] = discovery_info.hostname.upper().replace(
            "LAN_", ""
        )

        await self.async_set_unique_id(self.discovery_data[CONF_NAME])
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.discovery_data[CONF_HOST]}
        )

        # Abort if config_entry already exists without unigue_id configured.
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data[CONF_HOST] == self.discovery_data[CONF_HOST]
                and entry.unique_id is None
                and entry.state is ConfigEntryState.LOADED
            ):
                self.hass.config_entries.async_update_entry(
                    entry=entry,
                    unique_id=self.discovery_data[CONF_NAME],
                    data={**entry.data, **self.discovery_data},
                )
                return self.async_abort(reason="already_configured")
        self._async_abort_entries_match({CONF_HOST: self.discovery_data[CONF_HOST]})
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered Velux device."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _check_connection(
                self.discovery_data[CONF_HOST], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=self.discovery_data[CONF_NAME],
                    data={**self.discovery_data, **user_input},
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
            description_placeholders={
                "name": self.discovery_data[CONF_NAME],
                "host": self.discovery_data[CONF_HOST],
            },
        )
