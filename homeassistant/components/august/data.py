"""Support for August devices."""

from __future__ import annotations

from yalexs.lock import LockDetail
from yalexs.manager.data import YaleXSData
from yalexs_ble import YaleXSBLEDiscovery

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery_flow

from .gateway import AugustGateway

YALEXS_BLE_DOMAIN = "yalexs_ble"


@callback
def _async_trigger_ble_lock_discovery(
    hass: HomeAssistant, locks_with_offline_keys: list[LockDetail]
) -> None:
    """Update keys for the yalexs-ble integration if available."""
    for lock_detail in locks_with_offline_keys:
        discovery_flow.async_create_flow(
            hass,
            YALEXS_BLE_DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=YaleXSBLEDiscovery(
                {
                    "name": lock_detail.device_name,
                    "address": lock_detail.mac_address,
                    "serial": lock_detail.serial_number,
                    "key": lock_detail.offline_key,
                    "slot": lock_detail.offline_slot,
                }
            ),
        )


class AugustData(YaleXSData):
    """August data object."""

    def __init__(self, hass: HomeAssistant, august_gateway: AugustGateway) -> None:
        """Init August data object."""
        self._hass = hass
        super().__init__(august_gateway, HomeAssistantError)

    @callback
    def async_offline_key_discovered(self, detail: LockDetail) -> None:
        """Handle offline key discovery."""
        _async_trigger_ble_lock_discovery(self._hass, [detail])
