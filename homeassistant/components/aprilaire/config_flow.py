"""Config flow for the Aprilaire integration."""

from typing import Any, override

import probatio
from pyaprilaire.client import AprilaireClient, AprilaireResponseError
from pyaprilaire.const import Attribute

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, WAIT_TIMEOUT

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=7000): probatio.Port(),
    }
)


async def _async_read_mac_address(host: str, port: int) -> str | None:
    """Connect to the thermostat and return its MAC address."""
    client = AprilaireClient(host, port, lambda data: None)
    try:
        await client.start_listen_once()
        data = await client.read_mac_address_and_wait(WAIT_TIMEOUT)
    except OSError, AprilaireResponseError:
        return None
    finally:
        client.stop_listen()

    if not data or Attribute.MAC_ADDRESS not in data:
        return None
    return format_mac(data[Attribute.MAC_ADDRESS])


class AprilaireConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aprilaire."""

    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        if mac_address := await _async_read_mac_address(
            user_input[CONF_HOST], user_input[CONF_PORT]
        ):
            await self.async_set_unique_id(mac_address)

            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="AprilAire", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors={"base": "connection_failed"},
        )
