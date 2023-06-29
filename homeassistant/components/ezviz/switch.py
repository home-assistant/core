"""Support for EZVIZ Switch sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyezviz.constants import DeviceSwitchType, SupportExt
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity


@dataclass
class EzvizSwitchEntityDescriptionMixin:
    """Mixin values for EZVIZ Switch entities."""

    supported_ext: str | None


@dataclass
class EzvizSwitchEntityDescription(
    SwitchEntityDescription, EzvizSwitchEntityDescriptionMixin
):
    """Describe a EZVIZ switch."""


SWITCH_TYPES: dict[str, EzvizSwitchEntityDescription] = {
    "305": EzvizSwitchEntityDescription(
        key="305",
        name="Light PIR motion activated",
        device_class=SwitchDeviceClass.SWITCH,
        supported_ext=str(SupportExt.SupportLightRelate.value),
    ),
    "3": EzvizSwitchEntityDescription(
        key="3",
        name="Camera status light",
        device_class=SwitchDeviceClass.SWITCH,
        supported_ext=None,
    ),
}


ALARM_TONE = 1
LIGHT = 3
INTELLIGENT_ANALYSIS = 4
LOG_UPLOAD = 5
DEFENCE_PLAN = 6
PRIVACY = 7
SOUND_LOCALIZATION = 8
CRUISE = 9
INFRARED_LIGHT = 10
WIFI = 11
WIFI_MARKETING = 12
WIFI_LIGHT = 13
PLUG = 14
SLEEP = 21
SOUND = 22
BABY_CARE = 23
LOGO = 24
MOBILE_TRACKING = 25
CHANNELOFFLINE = 26
ALL_DAY_VIDEO = 29
AUTO_SLEEP = 32
ROAMING_STATUS = 34
DEVICE_4G = 35
ALARM_REMIND_MODE = 37
OUTDOOR_RINGING_SOUND = 39
INTELLIGENT_PQ_SWITCH = 40
DOORBELL_TALK = 101
HUMAN_INTELLIGENT_DETECTION = 200
LIGHT_FLICKER = 301
DEVICE_HUMAN_RELATE_LIGHT = 41
TAMPER_ALARM = 306
DETECTION_TYPE = 451
OUTLET_RECOVER = 600
CHIME_INDICATOR_LIGHT = 611
TRACKING = 650
CRUISE_TRACKING = 651
FEATURE_TRACKING = 701


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ switch based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        [
            EzvizSwitch(coordinator, camera, switch)
            for camera in coordinator.data
            for switch in coordinator.data[camera].get("switches")
            if switch in SWITCH_TYPES
            if SWITCH_TYPES[switch].supported_ext
            in coordinator.data[camera]["supportExt"]
            or SWITCH_TYPES[switch].supported_ext is None
        ]
    )


class EzvizSwitch(EzvizEntity, SwitchEntity):
    """Representation of a EZVIZ sensor."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, serial: str, switch: int
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, serial)
        self._name = switch
        self._attr_unique_id = (
            f"{serial}_{self._camera_name}.{DeviceSwitchType(switch).name}"
        )
        self.entity_description = SWITCH_TYPES[str(switch)]

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
