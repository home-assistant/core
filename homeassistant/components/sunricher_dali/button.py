"""Support for Sunricher DALI device identify button."""

from __future__ import annotations

import logging

from PySrDaliGateway import Device
from PySrDaliGateway.helper import is_light_device

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sunricher DALI button entities from config entry."""
    devices = entry.runtime_data.devices

    async_add_entities(
        DaliCenterIdentifyButton(device)
        for device in devices
        if is_light_device(device.dev_type)
    )


class DaliCenterIdentifyButton(DaliDeviceEntity, ButtonEntity):
    """Representation of a Sunricher DALI device identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Initialize the device identify button."""
        super().__init__(device)
        self._device = device
        self._attr_unique_id = f"{device.unique_id}_identify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device=(DOMAIN, device.gw_sn),
        )

    async def async_press(self) -> None:
        """Handle button press to identify device."""
        _LOGGER.debug("Identifying device %s", self._device.dev_id)
        self._device.identify()
