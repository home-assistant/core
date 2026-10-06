"""Represent Daikin Onecta gateway devices."""

import logging

from daikin_onecta.models import GatewayDevice, ManagementPoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DaikinOnectaDevice:
    """Class to represent and control one Daikin Onecta Device."""

    def __init__(self, device: GatewayDevice) -> None:
        """Initialize a new Daikin Onecta Device."""
        self.device = device
        self._is_present_in_cloud = True
        self.id: str = device.id
        self.name: str = device.display_name

        # Populated by async_register_ha_device() before any entity platform is set
        # up. Sub-entities (per-management-point devices in sensor/water_heater/
        # select/binary_sensor/switch/update) use this as via_device_id to link back
        # to this gateway device: the older via_device=(DOMAIN, identifier) form is
        # deprecated because identifiers are no longer guaranteed globally unique.
        self.ha_device_id: str | None = None

        _LOGGER.info(
            "Initialized Daikin Onecta Device '%s' (id %s)", self.name, self.id
        )

    @property
    def available(self) -> bool:
        """Return whether the device is connected to the Daikin cloud."""
        return self._is_present_in_cloud and self.device.available

    @property
    def gateway_embedded_id(self) -> str | None:
        """Return the embedded ID of the gateway management point."""
        return self.device.gateway_embedded_id

    def management_point(self, embedded_id: str) -> ManagementPoint | None:
        """Return a management point by embedded id."""
        return self.device.management_point(embedded_id)

    def fill_device_info(self, device_info: DeviceInfo, embedded_id: str) -> None:
        """Fill Home Assistant device information from an embedded management point ID."""
        device_info["manufacturer"] = "Daikin"
        point = self.device.management_point(embedded_id)
        if point is None:
            return
        if point.model is not None:
            device_info["model"] = point.model
        if point.serial is not None:
            device_info["serial_number"] = point.serial
        if point.version is not None:
            device_info["sw_version"] = point.version

    def fill_gateway_device_info(self, device_info: DeviceInfo) -> None:
        """Fill device information from the gateway management point."""
        device_info["manufacturer"] = "Daikin"
        if (embedded_id := self.gateway_embedded_id) is not None:
            self.fill_device_info(device_info, embedded_id)

    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        connections = set()
        if self.device.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, self.device.mac_address))

        info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.id)
            },
            connections=connections,
            name=self.name,
            model_id=self.device.device_model,
        )

        self.fill_gateway_device_info(info)
        return info

    def async_register_ha_device(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Eagerly create/update this device in the device registry.

        Called once from the coordinator, before any entity platform is set up
        (platforms are forwarded concurrently, so entity __init__ order across
        platforms can't be relied on). This guarantees self.ha_device_id is
        already populated by the time any platform builds a sub-device's
        DeviceInfo with via_device_id=self.ha_device_id.
        """
        device_registry = dr.async_get(hass)
        entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            **self.device_info(),
        )
        self.ha_device_id = entry.id

    def set_device_data(self, device: GatewayDevice) -> None:
        """Overwrite the typed and compatibility data for this device."""
        self.device = device
        self.name = device.display_name
        self._is_present_in_cloud = True
        _LOGGER.debug(
            "Device '%s' received new data from the Daikin cloud, isCloudConnectionUp '%s'",
            self.name,
            self.available,
        )

    def mark_unavailable(self) -> None:
        """Mark the device unavailable after it is absent from a cloud response."""
        self._is_present_in_cloud = False
