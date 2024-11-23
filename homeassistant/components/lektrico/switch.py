"""Support for Lektrico switch entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lektricowifi import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoSwitchEntityDescription(SwitchEntityDescription):
    """Describes Lektrico switch entity."""

    value_fn: Callable[[dict[str, Any]], bool]
    set_value_fn: Callable[[Device, dict[Any, Any], bool], Coroutine[Any, Any, Any]]


SWITCHS_FOR_ALL_CHARGERS: tuple[LektricoSwitchEntityDescription, ...] = (
    LektricoSwitchEntityDescription(
        key="authentication",
        translation_key="authentication",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: bool(data["require_auth"]),
        set_value_fn=lambda device, data, value: device.set_auth(not value),
    ),
    LektricoSwitchEntityDescription(
        key="lock",
        translation_key="lock",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: str(data["charger_state"]) == "locked",
        set_value_fn=lambda device, data, value: device.set_charger_locked(value),
    ),
)


SWITCHS_FOR_3_PHASE_CHARGERS: tuple[LektricoSwitchEntityDescription, ...] = (
    LektricoSwitchEntityDescription(
        key="force_single_phase",
        translation_key="force_single_phase",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data["relay_mode"] == 1,
        set_value_fn=lambda device, data, value: (
            device.set_relay_mode(data["dynamic_current"], 1)
            if value
            else device.set_relay_mode(data["dynamic_current"], 3)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico switch entities based on a config entry."""
    coordinator = entry.runtime_data

    switchs_to_be_used: tuple[LektricoSwitchEntityDescription, ...]
    if coordinator.device_type == Device.TYPE_3P22K:
        switchs_to_be_used = SWITCHS_FOR_ALL_CHARGERS + SWITCHS_FOR_3_PHASE_CHARGERS
    else:
        switchs_to_be_used = SWITCHS_FOR_ALL_CHARGERS

    async_add_entities(
        LektricoSwitch(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in switchs_to_be_used
    )


class LektricoSwitch(LektricoEntity, SwitchEntity):
    """Defines a Lektrico switch entity."""

    entity_description: LektricoSwitchEntityDescription

    def __init__(
        self,
        description: LektricoSwitchEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico switch."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_value_fn(
            self.coordinator.device, self.coordinator.data, True
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_value_fn(
            self.coordinator.device, self.coordinator.data, False
        )
        await self.coordinator.async_request_refresh()
