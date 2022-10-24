"""Config flow for Aranet4 integration."""
from __future__ import annotations

import logging
from typing import Any

from aranet4.client import Aranet4Advertisement, Version as AranetVersion
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_VERSION = AranetVersion(1, 2, 0)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aranet4."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up a new config flow for Aranet4."""
        self._discovered_devices: dict[str, tuple[str, Aranet4Advertisement]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            adv = self._discovered_devices[address][1]
            # Old versions of firmware don't expose sensor data in advertisements.
            if not adv.manufacturer_data or adv.manufacturer_data.version < MIN_VERSION:
                return self.async_abort(reason="outdated_version")

            # If integrations are disabled, we get no sensor data.
            if not adv.manufacturer_data.integrations:
                return self.async_abort(reason="integrations_disabled")

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address][0], data={}
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            print(discovery_info)
            if address in current_addresses or address in self._discovered_devices:
                continue

            # The aranet4 library expects the bleak format of objects, so if
            # they haven't been passed through from hass (often they are), we
            # generate them out of the discovery info.
            if hasattr(discovery_info, "device"):
                device = discovery_info.device
            else:
                device = BLEDevice(discovery_info.address, name=discovery_info.name)

            if hasattr(discovery_info, "advertisement"):
                ad_data = discovery_info.advertisement
            else:
                ad_data = AdvertisementData(
                    local_name=None,
                    manufacturer_data=discovery_info.manufacturer_data,
                    service_data=discovery_info.service_data,
                    service_uuids=discovery_info.service_uuids,
                    rssi=discovery_info.rssi,
                    tx_power=-127,
                    platform_data=(),
                )

            adv = Aranet4Advertisement(device, ad_data)
            if adv.manufacturer_data:
                self._discovered_devices[address] = (
                    adv.readings.name if adv.readings else discovery_info.name,
                    adv,
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            addr: dev[0]
                            for (addr, dev) in self._discovered_devices.items()
                        }
                    )
                }
            ),
        )
