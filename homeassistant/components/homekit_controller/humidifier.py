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
    SUPPORT_MODES,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

SUPPORT_FLAGS = 0

ATTR_DEHUMIDIFIER_THRESHOLD = "dehumidifier_threshold"
ATTR_HUMIDIFIER_THRESHOLD = "humidifier_threshold"
ATTR_CURRENT_HUMIDITY = "current_humidity"

MODE_OFF = "off"
MODE_HUMIDIFYING = "humidifying"
MODE_DEHUMIDIFYING = "dehumidifying"

HK_MODE_TO_HA = {
    0: MODE_OFF,
    1: MODE_AUTO,
    2: MODE_HUMIDIFYING,
    3: MODE_DEHUMIDIFYING,
}

HA_MODE_TO_HK = {
    MODE_AUTO: 0,
    MODE_HUMIDIFYING: 1,
    MODE_DEHUMIDIFYING: 2,
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
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD,
        ]

    def _char_threshold_for_current_mode(self):
        return (
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
            if self.device_class == DEVICE_CLASS_DEHUMIDIFIER
            or self.mode == MODE_DEHUMIDIFYING
            else CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        )

    @property
    def device_class(self) -> str:
        """Return the device class of the device."""
        dehumidifier_threshold = self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        )
        humidifier_threshold = self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        )

        if dehumidifier_threshold is not None and humidifier_threshold is not None:
            return None

        if dehumidifier_threshold is not None:
            return DEVICE_CLASS_DEHUMIDIFIER

        if humidifier_threshold is not None:
            return DEVICE_CLASS_HUMIDIFIER

        return None

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
            ATTR_MODE: self.mode,
            ATTR_HUMIDITY: self.target_humidity,
            ATTR_CURRENT_HUMIDITY: self.service.value(
                CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT
            ),
        }

        dehumidifier_threshold = self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        )
        if dehumidifier_threshold is not None:
            data[ATTR_DEHUMIDIFIER_THRESHOLD] = dehumidifier_threshold

        humidifier_threshold = self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        )
        if humidifier_threshold is not None:
            data[ATTR_HUMIDIFIER_THRESHOLD] = humidifier_threshold

        return data

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        return self.service.value(self._char_threshold_for_current_mode())

    @property
    def mode(self) -> Optional[str]:
        """Return the current mode, e.g., home, auto, baby.

        Requires SUPPORT_MODES.
        """
        mode = self.service.value(
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE
        )
        return HK_MODE_TO_HA.get(mode, "unknown")

    @property
    def available_modes(self) -> Optional[List[str]]:
        """Return a list of available modes.

        Requires SUPPORT_MODES.
        """
        available_modes = [
            MODE_OFF,
            MODE_AUTO,
        ]
        humidifier_threshold = self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
        )
        if humidifier_threshold is not None:
            available_modes.append(MODE_HUMIDIFYING)

        dehumidifier_threshold = self.service.value(
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
        )
        if dehumidifier_threshold is not None:
            available_modes.append(MODE_DEHUMIDIFYING)

        return available_modes

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.async_put_characteristics(
            {self._char_threshold_for_current_mode(): humidity}
        )

    async def async_set_mode(self, mode: str) -> None:
        """Set new mode."""

        if mode == MODE_OFF:
            await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})
        else:
            new_mode = HA_MODE_TO_HK.get(mode, "unknown")
            await self.async_put_characteristics(
                {CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: new_mode}
            )

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self.service[self._char_threshold_for_current_mode()].minValue

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self.service[self._char_threshold_for_current_mode()].maxValue


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit humidifer."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        if service["stype"] != "humidifier-dehumidifier":
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([HomeKitHumidifierDehumidifier(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
