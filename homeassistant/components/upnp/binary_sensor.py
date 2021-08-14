"""Support for UPnP/IGD Binary Sensors."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONFIG_ENTRY_SCAN_INTERVAL,
    CONFIG_ENTRY_UDN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DOMAIN_DEVICES,
    LOGGER as _LOGGER,
    UPTIME,
    WANIP,
    WANSTATUS,
)
from .device import Device


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    udn = config_entry.data[CONFIG_ENTRY_UDN]
    device: Device = hass.data[DOMAIN][DOMAIN_DEVICES][udn]

    update_interval_sec = config_entry.options.get(
        CONFIG_ENTRY_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )
    update_interval = timedelta(seconds=update_interval_sec)
    _LOGGER.debug("update_interval: %s", update_interval)
    _LOGGER.debug("Adding sensors")
    coordinator = DataUpdateCoordinator[Mapping[str, Any]](
        hass,
        _LOGGER,
        name=device.name,
        update_method=device.async_get_status,
        update_interval=update_interval,
    )
    device.coordinator = coordinator

    await coordinator.async_refresh()

    sensors = [
        UpnpStatusUpnpStatusBinarySensor(coordinator, device),
    ]
    async_add_entities(sensors, True)


class UpnpStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for UPnP/IGD binary sensors."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        device: Device,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._device = device

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and WANSTATUS in self.coordinator.data
            and self.coordinator.data[WANSTATUS] is not None
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.name} wan status"

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._device.udn}_wanstatus"

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def device_info(self) -> DeviceInfo:
        """Get device info."""
        return {
            "connections": {(dr.CONNECTION_UPNP, self._device.udn)},
            "name": self._device.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.model_name,
        }

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.coordinator.data[WANSTATUS] == "Connected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {}
        if self.coordinator.data[WANSTATUS] is not None:
            attributes.update({"WAN Status": self.coordinator.data[WANSTATUS]})
        if self.coordinator.data[WANIP] is not None:
            attributes.update({"WAN IP": self.coordinator.data[WANIP]})
        if self.coordinator.data[UPTIME] is not None:
            attributes.update({"Uptime": self.coordinator.data[UPTIME]})

        return attributes
