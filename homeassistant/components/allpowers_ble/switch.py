"""Allpowers BLE integration binary sensor platform."""


import asyncio

from allpowers_ble import AllpowersBLE

from homeassistant.components.light import LightEntity, LightEntityDescription
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AllpowersBLECoordinator
from .models import AllpowersBLEData

ENTITY_DESCRIPTIONS = [
    SwitchEntityDescription(
        key="ac_on",
        device_class=SwitchDeviceClass.OUTLET,
        has_entity_name=True,
        name="AC enabled",
    ),
    SwitchEntityDescription(
        key="dc_on",
        device_class=SwitchDeviceClass.OUTLET,
        has_entity_name=True,
        name="DC enabled",
    ),
]

LIGHT_DESCRIPTIONS = [
    LightEntityDescription(key="light_on", has_entity_name=True, name="Light enabled")
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for AllpowersBLE."""
    data: AllpowersBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AllpowersBLESwitch(data.coordinator, data.device, entry.title, description)
        for description in ENTITY_DESCRIPTIONS
    )

    async_add_entities(
        AllpowersBLELight(data.coordinator, data.device, entry.title, description)
        for description in LIGHT_DESCRIPTIONS
    )


class AllpowersBLESwitch(CoordinatorEntity, SwitchEntity):
    """Moving/static sensor for AllpowersBLE."""

    def __init__(
        self,
        coordinator: AllpowersBLECoordinator,
        device: AllpowersBLE,
        name: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._key = description.key
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = dr.DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._attr_is_on = getattr(self._device, self._key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = getattr(self._device, self._key)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Unavailable if coordinator isn't connected."""
        return self._coordinator.connected and super().available

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        if self._key == "ac_on":
            return self._device.ac_on
        if self._key == "dc_on":
            return self._device.dc_on
        if self._key == "light_on":
            return self._device.light_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        _switchap(self._device, self._key, True)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        _switchap(self._device, self._key, False)


def _switchap(device, key, status):
    if key == "ac_on":
        asyncio.run(device.set_ac(status))
    if key == "dc_on":
        asyncio.run(device.set_dc(status))
    if key == "light_on":
        asyncio.run(device.set_torch(status))


class AllpowersBLELight(CoordinatorEntity, LightEntity):
    """Moving/static sensor for AllpowersBLE."""

    def __init__(
        self,
        coordinator: AllpowersBLECoordinator,
        device: AllpowersBLE,
        name: str,
        description: LightEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._key = description.key
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = dr.DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._attr_is_on = getattr(self._device, self._key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = getattr(self._device, self._key)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Unavailable if coordinator isn't connected."""
        return self._coordinator.connected and super().available

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._device.light_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        asyncio.run(self._device.set_torch(True))

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        asyncio.run(self._device.set_torch(False))
