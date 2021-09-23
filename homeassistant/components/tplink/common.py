"""Common code for tplink."""
from __future__ import annotations

import logging
from typing import Any, Callable

from kasa import Discover, SmartDevice, SmartDeviceException

from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_DIMMER,
    CONF_LIGHT,
    CONF_STRIP,
    CONF_SWITCH,
    DOMAIN as TPLINK_DOMAIN,
    MAX_DISCOVERY_RETRIES,
)

_LOGGER = logging.getLogger(__name__)


class SmartDevices:
    """Hold different kinds of devices."""

    def __init__(
        self, lights: list[SmartDevice] = None, switches: list[SmartDevice] = None
    ) -> None:
        """Initialize device holder."""
        self._lights = lights or []
        self._switches = switches or []

    @property
    def lights(self) -> list[SmartDevice]:
        """Get the lights."""
        return self._lights

    @property
    def switches(self) -> list[SmartDevice]:
        """Get the switches."""
        return self._switches

    def has_device_with_host(self, host: str) -> bool:
        """Check if a devices exists with a specific host."""
        for device in self.lights + self.switches:
            if device.host == host:
                return True

        return False


async def async_get_discoverable_devices(hass: HomeAssistant) -> dict[str, SmartDevice]:
    """Return if there are devices that can be discovered."""

    return await Discover.discover()


async def async_discover_devices(
    hass: HomeAssistant, existing_devices: SmartDevices, target_device_count: int
) -> SmartDevices:
    """Get devices through discovery."""

    lights = []
    switches = []

    def process_devices() -> None:
        for device in devices.values():
            # If this device already exists, ignore dynamic setup.
            if existing_devices.has_device_with_host(device.host):
                continue

            if device.is_strip or device.is_plug:
                switches.append(device)
            if device.is_bulb or device.is_light_strip or device.is_dimmer:
                lights.append(device)
            else:
                _LOGGER.error("Unknown smart device type: %s", type(device))

    devices: dict[str, SmartDevice] = {}
    for attempt in range(1, MAX_DISCOVERY_RETRIES + 1):
        _LOGGER.debug(
            "Discovering tplink devices, attempt %s of %s",
            attempt,
            MAX_DISCOVERY_RETRIES,
        )
        discovered_devices = await async_get_discoverable_devices(hass)
        _LOGGER.info(
            "Discovered %s TP-Link of expected %s smart home device(s)",
            len(discovered_devices),
            target_device_count,
        )
        for device_ip in discovered_devices:
            devices[device_ip] = discovered_devices[device_ip]

        if len(discovered_devices) >= target_device_count:
            _LOGGER.info(
                "Discovered at least as many devices on the network as exist in our device registry, no need to retry"
            )
            break

    _LOGGER.info(
        "Found %s unique TP-Link smart home device(s) after %s discovery attempts",
        len(devices),
        attempt,
    )

    process_devices()

    return SmartDevices(lights, switches)


async def get_static_devices(config_data) -> SmartDevices:
    """Get statically defined devices in the config."""
    lights = []
    switches = []

    for type_ in (CONF_LIGHT, CONF_SWITCH, CONF_STRIP, CONF_DIMMER):
        for entry in config_data[type_]:
            host = entry["host"]
            try:
                device: SmartDevice = await Discover.discover_single(host)
                if device.is_bulb or device.is_light_strip or device.is_dimmer:
                    _LOGGER.debug("Found static light: %s", device)
                    lights.append(device)
                elif device.is_plug or device.is_strip:
                    _LOGGER.debug("Found static switch: %s", device)
                    switches.append(device)
            except SmartDeviceException as sde:
                _LOGGER.error(
                    "Failed to setup device %s due to %s; not retrying", host, sde
                )
    return SmartDevices(lights, switches)


# TODO is this still needed?
async def add_available_devices(
    hass: HomeAssistant, device_type: str, device_class: Callable
) -> list[Entity]:
    """Get sysinfo for all devices."""

    devices: list[SmartDevice] = hass.data[TPLINK_DOMAIN][device_type]

    if f"{device_type}_remaining" in hass.data[TPLINK_DOMAIN]:
        devices: list[SmartDevice] = hass.data[TPLINK_DOMAIN][
            f"{device_type}_remaining"
        ]

    entities_ready: list[Entity] = []
    devices_unavailable: list[SmartDevice] = []
    for device in devices:
        try:
            await device.update()
            entities_ready.append(device_class(device))
        except SmartDeviceException as ex:
            devices_unavailable.append(device)
            _LOGGER.warning(
                "Unable to communicate with device %s: %s",
                device.host,
                ex,
            )

    hass.data[TPLINK_DOMAIN][f"{device_type}_remaining"] = devices_unavailable
    return entities_ready


class CoordinatedTPLinkEntity(CoordinatorEntity):
    """Common base class for all coordinated tplink entities."""

    def __init__(self, device: SmartDevice, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device = device

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self.device.device_id

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Plug."""
        return self.device.alias

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        data = {
            "name": self.device.alias,
            "model": self.device.model,
            "manufacturer": "TP-Link",
            # Note: mac instead of device_id here to connect subdevices to the main device
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            "sw_version": self.device.hw_info["sw_ver"],
        }
        if self.device.is_strip_socket:
            data["via_device"] = self.device.parent.device_id

        return data

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.device.is_on
