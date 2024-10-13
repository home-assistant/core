"""Switch platform for Advantage Air integration."""

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdvantageAirDataConfigEntry
from .const import (
    ADVANTAGE_AIR_AUTOFAN_ENABLED,
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
)
from .entity import AdvantageAirAcEntity, AdvantageAirThingEntity
from .models import AdvantageAirData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AdvantageAirDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir switch platform."""

    instance = config_entry.runtime_data

    entities: list[SwitchEntity] = []
    if aircons := instance.coordinator.data.get("aircons"):
        for ac_key, ac_device in aircons.items():
            if ac_device["info"]["freshAirStatus"] != "none":
                entities.append(AdvantageAirFreshAir(instance, ac_key))
            if ADVANTAGE_AIR_AUTOFAN_ENABLED in ac_device["info"]:
                entities.append(AdvantageAirMyFan(instance, ac_key))
    if things := instance.coordinator.data.get("myThings"):
        entities.extend(
            AdvantageAirRelay(instance, thing)
            for thing in things["things"].values()
            if thing["channelDipState"] == 8  # 8 = Other relay
        )
    async_add_entities(entities)


class AdvantageAirFreshAir(AdvantageAirAcEntity, SwitchEntity):
    """Representation of Advantage Air fresh air control."""

    _attr_icon = "mdi:air-filter"
    _attr_name = "Fresh air"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, instance: AdvantageAirData, ac_key: str) -> None:
        """Initialize an Advantage Air fresh air control."""
        super().__init__(instance, ac_key)
        self._attr_unique_id += "-freshair"

    @property
    def is_on(self) -> bool:
        """Return the fresh air status."""
        return self._ac["freshAirStatus"] == ADVANTAGE_AIR_STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn fresh air on."""
        await self.async_update_ac({"freshAirStatus": ADVANTAGE_AIR_STATE_ON})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn fresh air off."""
        await self.async_update_ac({"freshAirStatus": ADVANTAGE_AIR_STATE_OFF})


class AdvantageAirMyFan(AdvantageAirAcEntity, SwitchEntity):
    """Representation of Advantage Air MyFan control."""

    _attr_icon = "mdi:fan-auto"
    _attr_name = "MyFan"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, instance: AdvantageAirData, ac_key: str) -> None:
        """Initialize an Advantage Air MyFan control."""
        super().__init__(instance, ac_key)
        self._attr_unique_id += "-myfan"

    @property
    def is_on(self) -> bool:
        """Return the MyFan status."""
        return self._ac[ADVANTAGE_AIR_AUTOFAN_ENABLED]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn MyFan on."""
        await self.async_update_ac({ADVANTAGE_AIR_AUTOFAN_ENABLED: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn MyFan off."""
        await self.async_update_ac({ADVANTAGE_AIR_AUTOFAN_ENABLED: False})


class AdvantageAirRelay(AdvantageAirThingEntity, SwitchEntity):
    """Representation of Advantage Air Thing."""

    _attr_device_class = SwitchDeviceClass.SWITCH
