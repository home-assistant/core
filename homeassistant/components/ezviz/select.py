"""Support for EZVIZ select controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyezvizapi.constants import (
    BatteryCameraWorkMode,
    DeviceCatagories,
    DeviceSwitchType,
    SoundMode,
    SupportExt,
)
from pyezvizapi.exceptions import HTTPError, PyEzvizError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EzvizSelectEntityDescription(SelectEntityDescription):
    """Describe a EZVIZ Select entity."""

    supported_switch: int
    current_option: Callable[[EzvizSelect], str | None]
    select_option: Callable[[EzvizSelect, str, str], None]


def alarm_sound_mode_current_option(ezvizSelect: EzvizSelect) -> str | None:
    """Return the selected entity option to represent the entity state."""
    sound_mode_value = getattr(
        SoundMode, ezvizSelect.data[ezvizSelect.entity_description.key]
    ).value
    if sound_mode_value in [0, 1, 2]:
        return ezvizSelect.options[sound_mode_value]

    return None


def alarm_sound_mode_select_option(
    ezvizSelect: EzvizSelect, serial: str, option: str
) -> None:
    """Change the selected option."""
    sound_mode_value = ezvizSelect.options.index(option)
    ezvizSelect.coordinator.ezviz_client.alarm_sound(serial, sound_mode_value, 1)


def battery_work_mode_current_option(ezvizSelect: EzvizSelect) -> str | None:
    """Return the selected entity option to represent the entity state."""
    battery_work_mode = getattr(
        BatteryCameraWorkMode,
        ezvizSelect.data[ezvizSelect.entity_description.key],
        BatteryCameraWorkMode.UNKNOWN,
    )
    if battery_work_mode == BatteryCameraWorkMode.UNKNOWN:
        return None

    return battery_work_mode.name.lower()


def battery_work_mode_select_option(
    ezvizSelect: EzvizSelect, serial: str, option: str
) -> None:
    """Change the selected option."""
    battery_work_mode = getattr(BatteryCameraWorkMode, option.upper())
    ezvizSelect.coordinator.ezviz_client.set_battery_camera_work_mode(
        serial, battery_work_mode.value
    )


ALARM_SOUND_MODE_SELECT_TYPE = EzvizSelectEntityDescription(
    key="alarm_sound_mod",
    translation_key="alarm_sound_mode",
    entity_category=EntityCategory.CONFIG,
    options=["soft", "intensive", "silent"],
    supported_switch=DeviceSwitchType.ALARM_TONE.value,
    current_option=alarm_sound_mode_current_option,
    select_option=alarm_sound_mode_select_option,
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
    current_option=battery_work_mode_current_option,
    select_option=battery_work_mode_select_option,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    for camera in coordinator.data:
        device_category = coordinator.data[camera].get("device_category")
        supportExt = coordinator.data[camera].get("supportExt")
        if (
            device_category == DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value
            and supportExt
            and str(SupportExt.SupportBatteryManage.value) in supportExt
        ):
            entities_to_add.append(
                EzvizSelect(coordinator, camera, BATTERY_WORK_MODE_SELECT_TYPE)
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
        return self.entity_description.current_option(self)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            return self.entity_description.select_option(self, self._serial, option)

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Cannot select option for {self.entity_description.key}"
            ) from err
