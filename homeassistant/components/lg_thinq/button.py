"""Support for button entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

ENABLE_BUTTON_STATE: dict[str, list[str]] = {
    "start": ["initial", "pause", "add_drain"],
    "stop": [
        "add_drain",
        "checking_turbidity",
        "cooling",
        "detecting",
        "detergent_amount",
        "dispensing",
        "display_loadsize",
        "drying",
        "end_cooling",
        "proofing",
        "preheat",
        "presteam",
        "prewash",
        "rinsing",
        "running",
        "shoes_module",
        "smart_grid_run",
        "soaking",
        "softening",
        "spinning",
        "stay",
        "steam",
        "steam_softening",
        "sterilize",
    ],
    "wake_up": ["sleep"],
}


@dataclass(frozen=True, kw_only=True)
class ThinQButtonEntityDescription(ButtonEntityDescription):
    """Describes ThinQ button entity."""

    value: Any


WASHER_OPERATION_DESC: tuple[ThinQButtonEntityDescription, ...] = (
    ThinQButtonEntityDescription(
        key=ThinQProperty.WASHER_OPERATION_MODE,
        translation_key="operation_mode_start",
        value="start",
    ),
    ThinQButtonEntityDescription(
        key=ThinQProperty.WASHER_OPERATION_MODE,
        translation_key="operation_mode_stop",
        value="stop",
    ),
    ThinQButtonEntityDescription(
        key=ThinQProperty.WASHER_OPERATION_MODE,
        translation_key="operation_mode_wake_up",
        value="wake_up",
    ),
)

DRYER_OPERATION_DESC: tuple[ThinQButtonEntityDescription, ...] = (
    ThinQButtonEntityDescription(
        key=ThinQProperty.DRYER_OPERATION_MODE,
        translation_key="operation_mode_start",
        value="start",
    ),
    ThinQButtonEntityDescription(
        key=ThinQProperty.DRYER_OPERATION_MODE,
        translation_key="operation_mode_stop",
        value="stop",
    ),
    ThinQButtonEntityDescription(
        key=ThinQProperty.DRYER_OPERATION_MODE,
        translation_key="operation_mode_wake_up",
        value="wake_up",
    ),
)

DEVICE_TYPE_BUTTON_MAP: dict[DeviceType, tuple[ThinQButtonEntityDescription, ...]] = {
    DeviceType.DISH_WASHER: (
        ThinQButtonEntityDescription(
            key=ThinQProperty.DISH_WASHER_OPERATION_MODE,
            translation_key="operation_mode_start",
            value="start",
        ),
        ThinQButtonEntityDescription(
            key=ThinQProperty.DISH_WASHER_OPERATION_MODE,
            translation_key="operation_mode_stop",
            value="stop",
        ),
    ),
    DeviceType.DRYER: DRYER_OPERATION_DESC,
    DeviceType.STYLER: (
        ThinQButtonEntityDescription(
            key=ThinQProperty.STYLER_OPERATION_MODE,
            translation_key="operation_mode_start",
            value="start",
        ),
        ThinQButtonEntityDescription(
            key=ThinQProperty.STYLER_OPERATION_MODE,
            translation_key="operation_mode_stop",
            value="stop",
        ),
        ThinQButtonEntityDescription(
            key=ThinQProperty.STYLER_OPERATION_MODE,
            translation_key="operation_mode_wake_up",
            value="wake_up",
        ),
    ),
    DeviceType.WASHCOMBO_MAIN: WASHER_OPERATION_DESC,
    DeviceType.WASHCOMBO_MINI: WASHER_OPERATION_DESC,
    DeviceType.WASHER: WASHER_OPERATION_DESC,
    DeviceType.WASHTOWER: WASHER_OPERATION_DESC + DRYER_OPERATION_DESC,
    DeviceType.WASHTOWER_DRYER: DRYER_OPERATION_DESC,
    DeviceType.WASHTOWER_WASHER: WASHER_OPERATION_DESC,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for button platform."""
    entities: list[ThinQButtonEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_BUTTON_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQButtonEntity(
                        coordinator, description, property_id, description.value
                    )
                    for property_id in coordinator.api.get_active_idx(
                        description.key,
                        ActiveMode.WRITABLE,
                        lambda state, value=description.value: value in state.options,
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQButtonEntity(ThinQEntity, ButtonEntity):
    """Represent a ThinQ button platform."""

    entity_description: ThinQButtonEntityDescription

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.device_state is None:
            return True
        states = ENABLE_BUTTON_STATE.get(self.entity_description.value)
        return (
            self.device_state.device_is_on
            and self.device_state.remote_control_enabled
            and (states is not None and self.device_state.state in states)
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug(
            "[%s:%s] async_press: %s",
            self.coordinator.device_name,
            self.property_id,
            self.entity_description.value,
        )
        if (value := self.entity_description.value) is not None:
            await self.async_call_api(
                self.coordinator.api.post(self.property_id, value)
            )
