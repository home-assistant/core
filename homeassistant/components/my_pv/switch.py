"""Creates Switch entities for the my-PV Home Assistant integration."""

from typing import Any, override

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyPVConfigEntry
from .const import DOMAIN
from .entity import MyPVSetupEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV switch."""
    coordinator = config_entry.runtime_data
    entities = []

    config = coordinator.device.get_setup_configuration("bstmode")
    if config and config.get("type") == "boolean":
        entity_description = SwitchEntityDescription(
            key="bstmode",
            device_class=SwitchDeviceClass.SWITCH,
            translation_key="bstmode",
        )
        entities.append(
            MyPVSwitch(
                coordinator,
                entity_description,
                coordinator.device.serial_number,
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
