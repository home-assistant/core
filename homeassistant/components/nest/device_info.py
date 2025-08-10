"""Library for extracting device specific information common to entities."""

from __future__ import annotations

from collections.abc import Mapping

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import ConnectivityTrait, InfoTrait

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONNECTIVITY_TRAIT_OFFLINE, DOMAIN

DEVICE_TYPE_MAP: dict[str, str] = {
    "sdm.devices.types.CAMERA": "Camera",
    "sdm.devices.types.DISPLAY": "Display",
    "sdm.devices.types.DOORBELL": "Doorbell",
    "sdm.devices.types.THERMOSTAT": "Thermostat",
}


class NestDeviceInfo:
    """Provide device info from the SDM device, shared across platforms."""

    device_brand = "Google Nest"

    def __init__(self, device: Device) -> None:
        """Initialize the DeviceInfo."""
        self._device = device

    @property
    def available(self) -> bool:
        """Return device availability."""
        if ConnectivityTrait.NAME in self._device.traits:
            trait: ConnectivityTrait = self._device.traits[ConnectivityTrait.NAME]
            if trait.status == CONNECTIVITY_TRAIT_OFFLINE:
                return False
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            # The API "name" field is a unique device identifier.
            identifiers={(DOMAIN, self._device.name)},
            manufacturer=self.device_brand,
            model=self.device_model,
            name=self.device_name,
            suggested_area=self.suggested_area,
        )

    @property
    def device_name(self) -> str | None:
        """Return the name of the physical device that includes the sensor."""
        if InfoTrait.NAME in self._device.traits:
            trait: InfoTrait = self._device.traits[InfoTrait.NAME]
            if trait.custom_name:
                return str(trait.custom_name)
        # Build a name from the room/structure if not set explicitly
        if area := self.suggested_area:
            return area
        return self.device_model

    @property
    def device_model(self) -> str | None:
        """Return device model information."""
        return DEVICE_TYPE_MAP.get(self._device.type) if self._device.type else None

    @property
    def suggested_area(self) -> str | None:
        """Return device suggested area based on the Google Home room."""
        if parent_relations := self._device.parent_relations:
            items = sorted(parent_relations.items())
            names = [name for _, name in items]
            return " ".join(names)
        return None


@callback
def async_nest_devices(hass: HomeAssistant) -> Mapping[str, Device]:
    """Return a mapping of all nest devices for all config entries."""
    return {
        device.name: device
        for config_entry in hass.config_entries.async_loaded_entries(DOMAIN)
        for device in config_entry.runtime_data.device_manager.devices.values()
    }


@callback
def async_nest_devices_by_device_id(hass: HomeAssistant) -> Mapping[str, Device]:
    """Return a mapping of all nest devices by home assistant device id, for all config entries."""
    device_registry = dr.async_get(hass)
    devices = {}
    for nest_device_id, device in async_nest_devices(hass).items():
        if device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, nest_device_id)}
        ):
            devices[device_entry.id] = device
    return devices
