"""Common utilities for VeSync Component."""
import abc
from itertools import chain
import logging
from typing import Any, Generic, TypeVar

from pyvesync.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.vesyncfan import humid_features

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity, ToggleEntity

from .const import (
    DOMAIN,
    VS_BINARY_SENSORS,
    VS_FANS,
    VS_HUMIDIFIERS,
    VS_LIGHTS,
    VS_NUMBERS,
    VS_SENSORS,
    VS_SWITCHES,
)

_LOGGER = logging.getLogger(__name__)


def get_domain_data(hass: HomeAssistant, config_entry: ConfigEntry, key: str) -> Any:
    """Get value of this domain's data."""
    if DOMAIN in hass.data and key in hass.data[DOMAIN]:
        return hass.data[DOMAIN][key]
    return None


class VeSyncDeviceHelper:
    """Collection of VeSync device helpers."""

    humidifier_models: set | None = None

    def get_feature(
        self, device: VeSyncBaseDevice, dictionary: str, attribute: str
    ) -> Any:
        """Return the value of the feature."""
        return getattr(device, dictionary, {}).get(attribute, None)

    def has_feature(
        self, device: VeSyncBaseDevice, dictionary: str, attribute: str
    ) -> bool:
        """Return true if the feature is available."""
        return self.get_feature(device, dictionary, attribute) is not None

    def is_humidifier(self, device_type: str) -> bool:
        """Return true if the device type is a humidifier."""
        if self.humidifier_models is None:
            # cache the model list after the first use
            self.humidifier_models = set(
                chain(*[features["models"] for features in humid_features.values()]),
            ).union(set(humid_features.keys()))
            _LOGGER.debug(
                "Initialized humidifier_models cache with %d models",
                len(self.humidifier_models),
            )

        return device_type in self.humidifier_models

    def reset_cache(self) -> None:
        """Reset the helper caches."""
        self.humidifier_models = None


DEVICE_HELPER = VeSyncDeviceHelper()


async def async_process_devices(hass, manager):
    """Assign devices to proper component."""
    devices = {}
    devices[VS_SWITCHES] = []
    devices[VS_BINARY_SENSORS] = []
    devices[VS_FANS] = []
    devices[VS_HUMIDIFIERS] = []
    devices[VS_NUMBERS] = []
    devices[VS_LIGHTS] = []
    devices[VS_SENSORS] = []

    await hass.async_add_executor_job(manager.update)

    if manager.fans:
        for fan in manager.fans:
            # VeSync classifies humidifiers as fans
            if DEVICE_HELPER.is_humidifier(fan.device_type):
                devices[VS_HUMIDIFIERS].append(fan)
            else:
                devices[VS_FANS].append(fan)
            devices[VS_SWITCHES].append(fan)  # for automatic stop and display
            devices[VS_LIGHTS].append(fan)  # for night light
            devices[VS_SENSORS].append(fan)
            devices[VS_NUMBERS].append(fan)  # for night light and mist level
            devices[VS_BINARY_SENSORS].append(fan)
        _LOGGER.info("%d VeSync fans found", len(devices[VS_FANS]))
        _LOGGER.info("%d VeSync humidifiers found", len(devices[VS_HUMIDIFIERS]))

    if manager.bulbs:
        devices[VS_LIGHTS].extend(manager.bulbs)
        _LOGGER.info("%d VeSync lights found", len(manager.bulbs))

    if manager.outlets:
        devices[VS_SWITCHES].extend(manager.outlets)
        # Expose outlets' voltage, power & energy usage as separate sensors
        devices[VS_SENSORS].extend(manager.outlets)
        _LOGGER.info("%d VeSync outlets found", len(manager.outlets))

    if manager.switches:
        for switch in manager.switches:
            if not switch.is_dimmable():
                devices[VS_SWITCHES].append(switch)
            else:
                devices[VS_LIGHTS].append(switch)
        _LOGGER.info("%d VeSync switches found", len(manager.switches))

    return devices


class VeSyncBaseEntity(Entity):
    """Base class for VeSync Entity Representations."""

    device: VeSyncBaseDevice

    def __init__(self, device: VeSyncBaseDevice) -> None:
        """Initialize the VeSync device."""
        self.device = device
        self._attr_unique_id = self.base_unique_id
        self._attr_name = self.base_name

    @property
    def base_unique_id(self):
        """Return the ID of this device."""
        # The unique_id property may be overridden in subclasses, such as in
        # sensors. Maintaining base_unique_id allows us to group related
        # entities under a single device.
        if isinstance(self.device.sub_device_no, int):
            return f"{self.device.cid}{str(self.device.sub_device_no)}"
        return self.device.cid

    @property
    def base_name(self) -> str:
        """Return the name of the device."""
        # Same story here as `base_unique_id` above
        return self.device.device_name

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.device.connection_status == "online"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            name=self.base_name,
            model=self.device.device_type,
            default_manufacturer="VeSync",
            sw_version=self.device.current_firm_version,
        )

    def update(self) -> None:
        """Update vesync device."""
        self.device.update()


class VeSyncDevice(VeSyncBaseEntity, ToggleEntity):
    """Base class for VeSync Device Representations."""

    @property
    def details(self):
        """Provide access to the device details dictionary."""
        return self.device.details

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.device_status == "on"

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.device.turn_off()


T = TypeVar("T")


class VeSyncEntityDescriptionFactory(Generic[T], metaclass=abc.ABCMeta):
    """Describe a factory interface for creating EntityDescription objects."""

    @classmethod
    def __subclasshook__(cls, subclass):
        """Impl of meta data."""
        return (
            hasattr(subclass, "create")
            and callable(subclass.create)
            and hasattr(subclass, "supports")
            and callable(subclass.supports)
        )

    @abc.abstractmethod
    def create(self, device: VeSyncBaseDevice) -> T:
        """Interface method for create."""

    @abc.abstractmethod
    def supports(self, device: VeSyncBaseDevice) -> bool:
        """Interface method for supports."""
