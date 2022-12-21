"""Support for EZVIZ Switch sensors."""
from __future__ import annotations

from typing import Any

from pyezviz.constants import DeviceSwitchType
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ switch based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    supported_switches = {switches.value for switches in DeviceSwitchType}

    async_add_entities(
        [
            EzvizSwitch(coordinator, camera, switch)
            for camera in coordinator.data
            for switch in coordinator.data[camera].get("switches")
            if switch in supported_switches
        ]
    )


class EzvizSwitch(EzvizEntity, SwitchEntity):
    """Representation of a EZVIZ sensor."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, serial: str, switch: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, serial)
        self._name = switch
        self._attr_name = f"{self._camera_name} {DeviceSwitchType(switch).name.title()}"
        self._attr_unique_id = (
            f"{serial}_{self._camera_name}.{DeviceSwitchType(switch).name}"
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.data["switches"][self._name]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Change a device switch on the camera."""
        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.switch_status, self._serial, self._name, 1
            )

        except (HTTPError, PyEzvizError) as err:
            raise PyEzvizError(f"Failed to turn on switch {self._name}") from err

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
