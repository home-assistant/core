"""Support for EZVIZ select controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyezvizapi.constants import (
    BatteryCameraWorkMode,
    DeviceCatagories,
    DeviceSwitchType,
    SoundMode,
)
from pyezvizapi.exceptions import HTTPError, PyEzvizError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1


class EzvizSelectEntityActionBase:
    """Base class to handle retrieval and selection of a EzvizSelectEntity."""

    current_option: Callable[[EzvizSelect], str | None]
    select_option: Callable[[EzvizSelect, str, str], None]


class AlarmSoundModeAction(EzvizSelectEntityActionBase):
    """Class dedicated to Alarm Sound Mode."""

    @staticmethod
    def current_option(ezvizSelect: EzvizSelect) -> str | None:
        """Return the selected entity option to represent the entity state."""
        sound_mode_value = getattr(
            SoundMode, ezvizSelect.data[ezvizSelect.entity_description.key]
        ).value
        if sound_mode_value in [0, 1, 2]:
            return ezvizSelect.options[sound_mode_value]

        return None

    @staticmethod
    def select_option(ezvizSelect: EzvizSelect, serial: str, option: str) -> None:
        """Change the selected option."""
        sound_mode_value = ezvizSelect.options.index(option)

        ezvizSelect.coordinator.ezviz_client.alarm_sound(serial, sound_mode_value, 1)


class BatteryWorkModeAction(EzvizSelectEntityActionBase):
    """Class dedicated to Battery Work Mode."""

    @staticmethod
    def current_option(ezvizSelect: EzvizSelect) -> str | None:
        """Return the selected entity option to represent the entity state."""
        battery_work_mode = getattr(
            BatteryCameraWorkMode,
            ezvizSelect.data[ezvizSelect.entity_description.key],
            BatteryCameraWorkMode.UNKNOWN,
        )
        if battery_work_mode == BatteryCameraWorkMode.UNKNOWN:
            return None

        return battery_work_mode.name.lower()

    @staticmethod
    def select_option(ezvizSelect: EzvizSelect, serial: str, option: str) -> None:
        """Change the selected option."""
        battery_work_mode = getattr(BatteryCameraWorkMode, option.upper())

        ezvizSelect.coordinator.ezviz_client.set_battery_camera_work_mode(
            serial, battery_work_mode.value
        )


@dataclass(frozen=True, kw_only=True)
class EzvizSelectEntityDescription(SelectEntityDescription):
    """Describe a EZVIZ Select entity."""

    supported_switch: int
    action_handler: type[EzvizSelectEntityActionBase]


ALARM_SOUND_MODE_SELECT_TYPE = EzvizSelectEntityDescription(
    key="alarm_sound_mod",
    translation_key="alarm_sound_mode",
    entity_category=EntityCategory.CONFIG,
    options=["soft", "intensive", "silent"],
    supported_switch=DeviceSwitchType.ALARM_TONE.value,
    action_handler=AlarmSoundModeAction,
)

BATTERY_WORK_MODE_SELECT_TYPE = EzvizSelectEntityDescription(
    key="battery_camera_work_mode",
    translation_key="battery_camera_work_mode",
    icon="mdi:battery-sync",
    entity_category=EntityCategory.CONFIG,
    options=[
        "plugged_in",
        "high_performance",
        "power_save",
        "super_power_save",
        "custom",
    ],
    supported_switch=-1,
    action_handler=BatteryWorkModeAction,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EZVIZ select entities based on a config entry."""
    coordinator = entry.runtime_data

    entities_to_add: list[EzvizSelect] = []

    entities_to_add.extend(
        EzvizSelect(coordinator, camera, ALARM_SOUND_MODE_SELECT_TYPE)
        for camera in coordinator.data
        for switch in coordinator.data[camera]["switches"]
        if switch == ALARM_SOUND_MODE_SELECT_TYPE.supported_switch
    )

    entities_to_add.extend(
        EzvizSelect(coordinator, camera, BATTERY_WORK_MODE_SELECT_TYPE)
        for camera in coordinator.data
        if coordinator.data[camera]["device_category"]
        == DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value
    )

    async_add_entities(entities_to_add)


class EzvizSelect(EzvizEntity, SelectEntity):
    """Representation of a EZVIZ select entity."""

    entity_description: EzvizSelectEntityDescription

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        description: EzvizSelectEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_{description.key}"
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.action_handler.current_option(self)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            return self.entity_description.action_handler.select_option(
                self, self._serial, option
            )

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Cannot select option for {self.entity_description.key}"
            ) from err
