"""Config flow for Kuler Sky."""

import logging
from typing import Any

from bluetooth_data_tools import human_readable_name
import pykulersky
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_last_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, EXPECTED_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class KulerskyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kulersky."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, str]
    ) -> ConfigFlowResult:
        """Handle the integration discovery step.

        The old version of the integration used to have multiple
        device in a single config entry. This is now deprecated.
        The integration discovery step is used to create config
        entries for each device beyond the first one.
        """
        address: str = discovery_info[CONF_ADDRESS]
        if service_info := async_last_service_info(self.hass, address):
            title = human_readable_name(None, service_info.name, service_info.address)
        else:
            title = address
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=title,
            data={CONF_ADDRESS: address},
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
        }
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            local_name = human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
            await self.async_set_unique_id(
                discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()

            kulersky_light = None
            try:
                kulersky_light = pykulersky.Light(discovery_info.address)
                await kulersky_light.connect()
            except pykulersky.PykulerskyException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=local_name,
                    data={
                        CONF_ADDRESS: discovery_info.address,
                    },
                )
            finally:
                if kulersky_light:
                    await kulersky_light.disconnect()

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.address in current_addresses
                    or discovery.address in self._discovered_devices
                    or EXPECTED_SERVICE_UUID not in discovery.service_uuids
                ):
                    continue
                self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        if self._discovery_info:
            data_schema = vol.Schema(
                {vol.Required(CONF_ADDRESS): self._discovery_info.address}
            )
        else:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            service_info.address: (
                                f"{service_info.name} ({service_info.address})"
                            )
                            for service_info in self._discovered_devices.values()
                        }
                    ),
                }
            )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
