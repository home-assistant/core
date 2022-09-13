"""Support for HomeKit Controller humidifier."""
from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
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


class HomeKitHumidifier(HomeKitEntity, HumidifierEntity):
    """Representation of a HomeKit Controller Humidifier."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD,
        ]

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified valve on."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        )

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
    def available_modes(self) -> list[str] | None:
        """Return a list of available modes.

        Requires HumidifierEntityFeature.MODES.
        """
        available_modes = [
            MODE_NORMAL,
            MODE_AUTO,
        ]

        return available_modes

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD: humidity}
        )

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
                    CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
                    CharacteristicsTypes.ACTIVE: True,
                }
            )

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return int(
            self.service[
                CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
            ].minValue
            or DEFAULT_MIN_HUMIDITY
        )

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return int(
            self.service[
                CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
            ].maxValue
            or DEFAULT_MAX_HUMIDITY
        )


class HomeKitDehumidifier(HomeKitEntity, HumidifierEntity):
    """Representation of a HomeKit Controller Humidifier."""

    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD,
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD,
        ]

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified valve on."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        )

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
    def available_modes(self) -> list[str] | None:
        """Return a list of available modes.

        Requires HumidifierEntityFeature.MODES.
        """
        available_modes = [
            MODE_NORMAL,
            MODE_AUTO,
        ]

        return available_modes

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD: humidity}
        )

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
                    CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
                    CharacteristicsTypes.ACTIVE: True,
                }
            )

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return int(
            self.service[
                CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
            ].minValue
            or DEFAULT_MIN_HUMIDITY
        )

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return int(
            self.service[
                CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
            ].maxValue
            or DEFAULT_MAX_HUMIDITY
        )

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-{self._iid}-{self.device_class}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit humidifer."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.HUMIDIFIER_DEHUMIDIFIER:
            return False

        info = {"aid": service.accessory.aid, "iid": service.iid}

        entities: list[HumidifierEntity] = []

        if service.has(CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD):
            entities.append(HomeKitHumidifier(conn, info))

        if service.has(CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD):
            entities.append(HomeKitDehumidifier(conn, info))

        async_add_entities(entities, True)

        return True

    conn.add_listener(async_add_service)
