"""Config flow for Qube Heat Pump integration."""

from typing import Any, override

import probatio
from python_qube_heatpump import QubeClient, async_get_device_info

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN, MDNS_LOOKUP_TIMEOUT


class QubeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qube Heat Pump."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            self._async_abort_entries_match({CONF_HOST: host})

            # Connect and verify it's a Qube by reading software version
            client = QubeClient(host, DEFAULT_PORT)
            try:
                connected = await client.connect()
                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    version = await client.async_get_software_version()
                    if version is None:
                        errors["base"] = "not_qube_device"
            except OSError:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()

            if not errors:
                # The controller's mDNS record carries a stable uuid; without
                # mDNS (e.g. across VLANs) the entry is created without one
                aiozc = await zeroconf.async_get_async_instance(self.hass)
                if device := await async_get_device_info(
                    host, aiozc, timeout=MDNS_LOOKUP_TIMEOUT
                ):
                    await self.async_set_unique_id(device.uuid)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Qube heat pump",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: DEFAULT_PORT,
                    },
                )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_HOST): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
