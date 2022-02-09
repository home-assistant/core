"""WiZ integration binary sensor platform."""
from __future__ import annotations

from collections.abc import Callable

from pywizlight.bulb import PIR_SOURCE

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SIGNAL_WIZ_PIR
from .models import WizData

OCCUPANCY_UNIQUE_ID = "{}_occupancy"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WiZ binary sensor platform."""
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    mac = wiz_data.bulb.mac

    if er.async_get(hass).async_get_entity_id(
        DOMAIN, Platform.BINARY_SENSOR, OCCUPANCY_UNIQUE_ID.format(mac)
    ):
        async_add_entities([WizOccupancyEntity(wiz_data, entry.title)])
        return

    cancel_dispatcher: Callable[[], None] | None = None

    @callback
    def _async_add_montion_sensor() -> None:
        assert cancel_dispatcher is not None
        cancel_dispatcher()
        async_add_entities([WizOccupancyEntity(wiz_data, entry.title)])

    cancel_dispatcher = async_dispatcher_connect(
        hass, SIGNAL_WIZ_PIR.format(mac), _async_add_montion_sensor
    )
    entry.async_on_unload(cancel_dispatcher)


class WizOccupancyEntity(CoordinatorEntity, BinarySensorEntity):
    """Representation of WiZ Occupancy sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize an WiZ device."""
        super().__init__(wiz_data.coordinator)
        self._device = wiz_data.bulb
        self._attr_unique_id = OCCUPANCY_UNIQUE_ID.format(self._device.mac)
        self._attr_name = f"{name} Occupancy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="WiZ",
            via_device=(DOMAIN, self._device.mac),
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        if self._device.state.get_source() == PIR_SOURCE:
            self._attr_is_on = self._device.state
