"""Support for Ezviz Switch sensors."""
from __future__ import annotations

import logging
from typing import Any

from pyezviz.constants import DeviceSwitchType
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.switch import DEVICE_CLASS_SWITCH, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ezviz switch based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    switch_entities = []
    supported_switches = {switches.value for switches in DeviceSwitchType}

    for idx, camera in enumerate(coordinator.data):
        if not camera.get("switches"):
            continue
        for switch in camera["switches"]:
            if switch not in supported_switches:
                continue
            switch_entities.append(EzvizSwitch(coordinator, idx, switch))

    async_add_entities(switch_entities)


class EzvizSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Ezviz sensor."""

    coordinator: EzvizDataUpdateCoordinator

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, idx: int, switch: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._idx = idx
        self._camera_name = self.coordinator.data[self._idx]["name"]
        self._name = switch
        self._sensor_name = f"{self._camera_name}.{DeviceSwitchType(self._name).name}"
        self._serial = self.coordinator.data[self._idx]["serial"]
        self._device_class = DEVICE_CLASS_SWITCH

    @property
    def name(self) -> str:
        """Return the name of the Ezviz switch."""
        return f"{DeviceSwitchType(self._name).name}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.coordinator.data[self._idx]["switches"][self._name]

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this switch."""
        return f"{self._serial}_{self._sensor_name}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Change a device switch on the camera."""
        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.switch_status, self._serial, self._name, 1
            )

        except (HTTPError, PyEzvizError) as err:
            raise PyEzvizError("Failed to turn on switch {self._name}") from err

        if update_ok:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Change a device switch on the camera."""
        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.switch_status, self._serial, self._name, 0
            )

        except (HTTPError, PyEzvizError) as err:
            raise PyEzvizError(f"Failed to turn off switch {self._name}") from err

        if update_ok:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": self.coordinator.data[self._idx]["name"],
            "model": self.coordinator.data[self._idx]["device_sub_category"],
            "manufacturer": MANUFACTURER,
            "sw_version": self.coordinator.data[self._idx]["version"],
        }

    @property
    def device_class(self) -> str:
        """Device class for the sensor."""
        return self._device_class
