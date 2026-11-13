"""Support for Sunricher DALI device identify button."""

import logging
from typing import override

from PySrDaliGateway import Device
from PySrDaliGateway.helper import is_light_device

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
        DaliCenterIdentifyButton(hass, device, entry)
        for device in devices
        if is_light_device(device.dev_type)
    )


class DaliCenterIdentifyButton(DaliDeviceEntity, ButtonEntity):
    """Representation of a Sunricher DALI device identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = None

    def __init__(
        self, hass: HomeAssistant, device: Device, entry: DaliCenterConfigEntry
    ) -> None:
        """Initialize the device identify button."""
        super().__init__(hass, device, entry)
        self._attr_unique_id = f"{device.unique_id}_identify"

    @override
    async def async_press(self) -> None:
        """Handle button press to identify device."""
        _LOGGER.debug("Identifying device %s", self._device.dev_id)
        self._device.identify()
