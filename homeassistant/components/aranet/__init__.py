"""The Aranet integration."""

from __future__ import annotations

import logging

from aranet4.client import Aranet4Advertisement

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type AranetConfigEntry = ConfigEntry[
    PassiveBluetoothProcessorCoordinator[Aranet4Advertisement]
]


def _service_info_to_adv(
    service_info: BluetoothServiceInfoBleak,
) -> Aranet4Advertisement:
    return Aranet4Advertisement(service_info.device, service_info.advertisement)


async def async_setup_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Set up Aranet from a config entry."""

    address = entry.unique_id
    assert address is not None
    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=_service_info_to_adv,
    )
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
