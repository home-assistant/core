"""Creates Switch entities for the my-PV integration."""

from typing import Any, Final, override

from my_pv import MyPVDeviceMainMode

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MyPVConfigEntry
from .entity import MyPVBaseEntity, MyPVSetupEntity

PARALLEL_UPDATES = 0

ENTITY_DESCRIPTIONS: Final[tuple[SwitchEntityDescription, ...]] = (
    SwitchEntityDescription(
        key="bstmode",
        entity_category=EntityCategory.CONFIG,
        device_class=SwitchDeviceClass.SWITCH,
        translation_key="bstmode",
    ),
)

DEVMODE_DESCRIPTION: Final = SwitchEntityDescription(
    key="devmode",
    device_class=SwitchDeviceClass.SWITCH,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV switch."""
    coordinator = config_entry.runtime_data
    entities: list[SwitchEntity] = [
        MyPVSwitch(coordinator, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        if (
            config := coordinator.device.get_setup_configuration(entity_description.key)
        )
        and config.get("type") == "boolean"
    ]

    if (
        coordinator.device.supports_main_mode(MyPVDeviceMainMode.HOT_WATER)
        and coordinator.device.current_temperature is None
    ):
        entities.append(
            MyPVWaterHeaterSwitch(
                coordinator,
                DEVMODE_DESCRIPTION,
            )
        )

    async_add_entities(entities)


class MyPVSwitch(MyPVSetupEntity, SwitchEntity):
    """my-PV switch."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        value = self.coordinator.device.get_setup_value(self.entity_description.key)
        return bool(value) if value is not None else None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not await self.coordinator.set_setup_value(
            self.entity_description.key, True
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if not await self.coordinator.set_setup_value(
            self.entity_description.key, False
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )


class MyPVWaterHeaterSwitch(MyPVBaseEntity, SwitchEntity):
    """my-PV water heater switch."""

    _attr_name = None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        return self.coordinator.device.is_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        if not await self.coordinator.turn_on():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        if not await self.coordinator.turn_off():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )
