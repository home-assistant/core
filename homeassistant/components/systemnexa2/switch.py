"""Switch entity for the SystemNexa2 integration."""

from dataclasses import dataclass
from typing import Any, Final

from sn2.device import OnOffSetting

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemNexa2ConfigEntry, SystemNexa2DataUpdateCoordinator
from .entity import SystemNexa2Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SystemNexa2SwitchEntityDescription(SwitchEntityDescription):
    """Entity description for SystemNexa switch entities."""


SWITCH_TYPES: Final = [
    SystemNexa2SwitchEntityDescription(
        key="433Mhz",
        translation_key="433mhz",
        entity_category=EntityCategory.CONFIG,
    ),
    SystemNexa2SwitchEntityDescription(
        key="Cloud Access",
        translation_key="cloud_access",
        entity_category=EntityCategory.CONFIG,
    ),
    SystemNexa2SwitchEntityDescription(
        key="Led",
        translation_key="led",
        entity_category=EntityCategory.CONFIG,
    ),
    SystemNexa2SwitchEntityDescription(
        key="Physical Button",
        translation_key="physical_button",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemNexa2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch and configuration options based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[SystemNexa2Entity] = [
        SystemNexa2ConfigurationSwitch(coordinator, switch_type, setting)
        for setting_name, setting in coordinator.data.on_off_settings.items()
        for switch_type in SWITCH_TYPES
        if switch_type.key == setting_name
    ]

    if coordinator.data.info_data.dimmable is False:
        entities.append(
            SystemNexa2SwitchPlug(
                coordinator=coordinator,
            )
        )
    async_add_entities(entities)


class SystemNexa2ConfigurationSwitch(SystemNexa2Entity, SwitchEntity):
    """Configuration switch entity for SystemNexa2 devices."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: SystemNexa2SwitchEntityDescription

    def __init__(
        self,
        coordinator: SystemNexa2DataUpdateCoordinator,
        description: SystemNexa2SwitchEntityDescription,
        setting: OnOffSetting,
    ) -> None:
        """Initialize the configuration switch."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._setting = setting

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.async_setting_enable(self._setting)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.async_setting_disable(self._setting)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.on_off_settings[
            self.entity_description.key
        ].is_enabled()


class SystemNexa2SwitchPlug(SystemNexa2Entity, SwitchEntity):
    """Representation of a Switch."""

    _attr_translation_key = "relay_1"

    def __init__(
        self,
        coordinator: SystemNexa2DataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator=coordinator,
            key="relay_1",
        )

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.async_turn_off()

    async def async_toggle(self, **_kwargs: Any) -> None:
        """Toggle the switch."""
        await self.coordinator.async_toggle()

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.coordinator.data.state is None:
            return None
        return bool(self.coordinator.data.state)
