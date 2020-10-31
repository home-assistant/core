"""Support for HomeKit Controller humidifier."""
from typing import Any, Dict, List, Optional

from aiohomekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_MODE,
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    MODE_AUTO,
    MODE_NORMAL,
    SUPPORT_MODES,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

SUPPORT_FLAGS = 0

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

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD,
        ]

    @property
    def device_class(self) -> str:
        """Return the device class of the device."""
        return DEVICE_CLASS_HUMIDIFIER

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS | SUPPORT_MODES

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    async def async_turn_on(self, **kwargs):
        """Turn the specified valve on."""
        await self.async_put_characteristics(
            {
                CharacteristicsTypes.ACTIVE: True,
                CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
            }
        )

    async def async_turn_off(self, **kwargs):
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def capability_attributes(self) -> Dict[str, Any]:
        """Return capability attributes."""
        data = {
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
            ATTR_AVAILABLE_MODES: self.available_modes,
        }

        return data

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        data = {
            ATTR_MODE: self.mode,
            ATTR_HUMIDITY: self.target_humidity,
        }

        return data

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        return self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        )

    @property
    def mode(self) -> Optional[str]:
        """Return the current mode, e.g., home, auto, baby.

        Requires SUPPORT_MODES.
        """
        mode = self.service.value(
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE
        )
        return MODE_AUTO if mode == 1 else MODE_NORMAL

    @property
    def available_modes(self) -> Optional[List[str]]:
        """Return a list of available modes.

        Requires SUPPORT_MODES.
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
            await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self.service[
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        ].minValue

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self.service[
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        ].maxValue


class HomeKitDehumidifier(HomeKitEntity, HumidifierEntity):
    """Representation of a HomeKit Controller Humidifier."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD,
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD,
        ]

    @property
    def device_class(self) -> str:
        """Return the device class of the device."""
        return DEVICE_CLASS_DEHUMIDIFIER

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS | SUPPORT_MODES

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    async def async_turn_on(self, **kwargs):
        """Turn the specified valve on."""
        await self.async_put_characteristics(
            {
                CharacteristicsTypes.ACTIVE: True,
                CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
            }
        )

    async def async_turn_off(self, **kwargs):
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def capability_attributes(self) -> Dict[str, Any]:
        """Return capability attributes."""
        data = {
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
            ATTR_AVAILABLE_MODES: self.available_modes,
        }

        return data

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        data = {
            ATTR_MODE: self.mode,
            ATTR_HUMIDITY: self.target_humidity,
        }

        return data

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        return self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        )

    @property
    def mode(self) -> Optional[str]:
        """Return the current mode, e.g., home, auto, baby.

        Requires SUPPORT_MODES.
        """
        mode = self.service.value(
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE
        )
        return MODE_AUTO if mode == 1 else MODE_NORMAL

    @property
    def available_modes(self) -> Optional[List[str]]:
        """Return a list of available modes.

        Requires SUPPORT_MODES.
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
            await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self.service[
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        ].minValue

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self.service[
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        ].maxValue

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-{self._iid}-{self.device_class}"


class HomeKitDiffuser(HomeKitEntity, HumidifierEntity):
    """Representation of a HomeKit Controller Humidifier."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE,
            CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL,
        ]

    @property
    def device_class(self) -> str:
        """Return the device class of the device."""
        return DEVICE_CLASS_HUMIDIFIER

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    async def async_turn_on(self, **kwargs):
        """Turn the specified valve on."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: True})

    async def async_turn_off(self, **kwargs):
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def capability_attributes(self) -> Dict[str, Any]:
        """Return capability attributes."""
        data = {
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
            ATTR_AVAILABLE_MODES: self.available_modes,
        }

        return data

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        data = {
            ATTR_HUMIDITY: self.service.value(
                CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL
            )
            * 20,
        }

        if not self.is_on:
            data[ATTR_HUMIDITY] = 0

        return data

    @property
    def available_modes(self) -> Optional[List[str]]:
        """Return a list of available modes.

        Requires SUPPORT_MODES.
        """
        return []

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        if not self.is_on:
            return 0

        return (
            self.service.value(
                CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL
            )
            * 20
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""

        if humidity < 20:
            await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})
        else:
            if not self.is_on:
                await self.async_put_characteristics(
                    {CharacteristicsTypes.ACTIVE: True}
                )

            await self.async_put_characteristics(
                {
                    CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: humidity
                    / 20
                }
            )

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return 0

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return 100


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit humidifer."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    def get_accessory(conn, aid):
        for acc in conn.accessories:
            if acc.get("aid") == aid:
                return acc
        return None

    def get_service(acc, iid):
        for serv in acc.get("services"):
            if serv.get("iid") == iid:
                return serv
        return None

    def get_char(serv, iid):
        try:
            type_name = CharacteristicsTypes[iid]
            type_uuid = CharacteristicsTypes.get_uuid(type_name)
            for char in serv.get("characteristics"):
                if char.get("type") == type_uuid:
                    return char
        except KeyError:
            return None
        return None

    @callback
    def async_add_service(aid, service):
        if service["stype"] != "humidifier-dehumidifier":
            return False
        info = {"aid": aid, "iid": service["iid"]}

        acc = get_accessory(conn, aid)
        serv = get_service(acc, service["iid"])

        if (
            get_char(serv, CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD)
            is not None
        ):
            async_add_entities([HomeKitHumidifier(conn, info)], True)

        if (
            get_char(
                serv, CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
            )
            is not None
        ):
            async_add_entities([HomeKitDehumidifier(conn, info)], True)

        return True

    conn.add_listener(async_add_service)
