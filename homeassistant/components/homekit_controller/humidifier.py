"""Support for HomeKit Controller humidifier."""

from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes
from propcache import cached_property

from homeassistant.components.humidifier import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    MODE_AUTO,
    MODE_NORMAL,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity

HK_MODE_TO_HA = {
    0: "off",
    1: MODE_AUTO,
    2: "humidifying",
    3: "dehumidifying",
}

HA_MODE_TO_HK = {
    MODE_AUTO: 0,
    "humidifying": 1,
    "dehumidifying": 2,
}


class HomeKitBaseHumidifier(HomeKitEntity, HumidifierEntity):
    """Representation of a HomeKit Controller Humidifier."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = [MODE_NORMAL, MODE_AUTO]
    _humidity_char = CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
    _on_mode_value = 1

    @callback
    def _async_reconfigure(self) -> None:
        """Reconfigure entity."""
        self._async_clear_property_cache(("max_humidity", "min_humidity"))
        super()._async_reconfigure()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    @property
    def mode(self) -> str | None:
        """Return the current mode, e.g., home, auto, baby.

        Requires HumidifierEntityFeature.MODES.
        """
        mode = self.service.value(
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE
        )
        return MODE_AUTO if mode == 1 else MODE_NORMAL

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.service.value(self._humidity_char)

    @cached_property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return int(self.service[self._humidity_char].minValue or DEFAULT_MIN_HUMIDITY)

    @cached_property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return int(self.service[self._humidity_char].maxValue or DEFAULT_MAX_HUMIDITY)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.async_put_characteristics({self._humidity_char: humidity})

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified valve on."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    async def async_set_mode(self, mode: str) -> None:
        """Set new mode."""
        if mode == MODE_AUTO:
            await self.async_put_characteristics(
                {
                    CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
                    CharacteristicsTypes.ACTIVE: True,
                }
            )
        else:
            await self.async_put_characteristics(
                {
                    CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: self._on_mode_value,
                    CharacteristicsTypes.ACTIVE: True,
                }
            )

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD,
        ]


class HomeKitHumidifier(HomeKitBaseHumidifier):
    """Representation of a HomeKit Controller Humidifier."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER


class HomeKitDehumidifier(HomeKitBaseHumidifier):
    """Representation of a HomeKit Controller Humidifier."""

    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER
    _humidity_char = CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
    _on_mode_value = 2

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise the dehumidifier."""
        super().__init__(accessory, devinfo)
        self._attr_unique_id = f"{accessory.unique_id}_{self._iid}_{self.device_class}"

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            *super().get_characteristic_types(),
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD,
        ]

    @property
    def old_unique_id(self) -> str:
        """Return the old ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-{self._iid}-{self.device_class}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit humidifer."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.HUMIDIFIER_DEHUMIDIFIER:
            return False

        info = {"aid": service.accessory.aid, "iid": service.iid}

        entities: list[HomeKitHumidifier | HomeKitDehumidifier] = []

        if service.has(CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD):
            entities.append(HomeKitHumidifier(conn, info))

        if service.has(CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD):
            entities.append(HomeKitDehumidifier(conn, info))

        for entity in entities:
            conn.async_migrate_unique_id(
                entity.old_unique_id, entity.unique_id, Platform.HUMIDIFIER
            )

        async_add_entities(entities)

        return True

    conn.add_listener(async_add_service)
