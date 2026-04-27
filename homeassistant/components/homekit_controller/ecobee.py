"""HomeKit Controller — ecobee vendor-specific entities.

All ecobee HAP entities and number descriptors are consolidated here.
Platform files import from this module instead of defining ecobee logic
inline, keeping ecobee concerns isolated from the generic HomeKit machinery.

Sensor descriptors live inline in sensor.py (not here) to avoid a circular
import; they carry a comment pointing back to this file.

Characteristic UUIDs are from aiohomekit's CharacteristicsTypes enum. The
SLEEP/AWAY UUIDs were swapped in aiohomekit ≤3.2.20 and corrected in our
fork (sirwolfgang/aiohomekit@patch/ecobee).

Hold semantics (confirmed empirically):
  - Mode hold (SET_HOLD_SCHEDULE): home=0, sleep=1, away=2
  - Timed hold: write TIMESTAMP first (trailing-T format), sleep 0.5s, then
    write SET_HOLD_SCHEDULE. Combined writes → ecobee defaults to permanent.
  - Permanent hold sentinel: "2035-01-03T00:00:00"
  - Clear hold: toggle CLEAR_HOLD false→true; also reset FAN_WRITE_SPEED=0
    because fan hold is independent of mode hold.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from typing import Any

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.helpers.typing import ConfigType

from .entity import CharacteristicEntity

_LOGGER = logging.getLogger(__name__)


# ── CHARACTERISTIC_PLATFORMS entries ──────────────────────────────────────────
# Ecobee platform mappings live inline in CHARACTERISTIC_PLATFORMS in const.py.
# They cannot be defined here and imported from const.py due to a circular
# import chain:
#   config_flow.py → const.py → ecobee.py → entity.py → connection.py → config_flow.py


# ── Number descriptors ─────────────────────────────────────────────────────────
# Merged into NUMBER_ENTITIES in number.py.

ECOBEE_NUMBER_ENTITIES: dict[str, NumberEntityDescription] = {
    CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_HEAT: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_HEAT,
        name="Home Heating Target",
        translation_key="ecobee_home_target_heat",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_COOL: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_COOL,
        name="Home Cooling Target",
        translation_key="ecobee_home_target_cool",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_HEAT: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_HEAT,
        name="Sleep Heating Target",
        translation_key="ecobee_sleep_target_heat",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_COOL: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_COOL,
        name="Sleep Cooling Target",
        translation_key="ecobee_sleep_target_cool",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_HEAT: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_HEAT,
        name="Away Heating Target",
        translation_key="ecobee_away_target_heat",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_COOL: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_COOL,
        name="Away Cooling Target",
        translation_key="ecobee_away_target_cool",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
}


# ── Mode select ────────────────────────────────────────────────────────────────

_ECOBEE_MODE_TO_TEXT: dict[int, str] = {0: "home", 1: "sleep", 2: "away"}
_ECOBEE_MODE_TO_NUMBERS: dict[str, int] = {v: k for k, v in _ECOBEE_MODE_TO_TEXT.items()}


class EcobeeModeSelect(CharacteristicEntity, SelectEntity):
    """Represents a ecobee mode select entity."""

    _attr_options = ["home", "sleep", "away"]
    _attr_translation_key = "ecobee_mode"

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        if name := super().name:
            return f"{name} Current Mode"
        return "Current Mode"

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return _ECOBEE_MODE_TO_TEXT.get(self._char.value)

    async def async_select_option(self, option: str) -> None:
        """Set the current mode."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: _ECOBEE_MODE_TO_NUMBERS[option]}
        )


# ── Clear hold button ──────────────────────────────────────────────────────────

class HomeKitEcobeeClearHoldButton(CharacteristicEntity, ButtonEntity):
    """A button that clears any active ecobee hold and resumes the schedule."""

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return []

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        prefix = ""
        if name := super().name:
            prefix = name
        return f"{prefix} Clear Hold"

    async def async_press(self) -> None:
        """Clear the active hold and resume the ecobee schedule.

        Toggles CLEAR_HOLD false→true: ecobee caches state and ignores a
        write that matches the current value, so the false→true sequence
        guarantees the request is processed.

        Fan hold is independent of mode hold — CLEAR_HOLD does not reset
        FAN_WRITE_SPEED, so we explicitly set it to 0 (auto) here.
        """
        key = self._char.type
        for val in (False, True):
            await self.async_put_characteristics({key: val})
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED: 0}
        )


# ── Hold expiration datetime ───────────────────────────────────────────────────

class EcobeeHoldUntilDatetime(CharacteristicEntity, DateTimeEntity):
    """Represents the ecobee hold-until datetime.

    Reads VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME (IID 41) which ecobee sets
    to the hold end time when a hold is active, or blank when following schedule.
    The permanent-hold sentinel is "2035-01-03T00:00:00".

    Writing sets a timed hold: the characteristic is written paired with
    VENDOR_ECOBEE_SET_HOLD_SCHEDULE so the ecobee applies the end time with
    the current comfort profile mode.
    """

    _attr_translation_key = "ecobee_hold_until"

    @property
    def name(self) -> str:
        """Return the entity name."""
        return f"{self.accessory.name} Hold Expiration"

    @property
    def available(self) -> bool:
        """Return True when the accessory is reachable.

        The base class marks the entity unavailable when the TIMESTAMP
        characteristic has no value (char.available is False). An empty
        TIMESTAMP just means no hold is active — the entity itself is
        working fine, so we bypass the char check.
        """
        return self._accessory.available

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME]

    @property
    def native_value(self) -> datetime | None:
        """Return the current hold-until datetime, or None when on schedule or on permanent hold."""
        raw: str = self._char.value
        if not raw:
            return None
        # Strip ecobee's trailing 'T' quirk: "2026-04-04T17:35:23-07:00T"
        raw = raw.rstrip("T")
        try:
            value = datetime.fromisoformat(raw)
        except ValueError:
            _LOGGER.debug("Could not parse ecobee TIMESTAMP value: %r", raw)
            return None
        # The permanent-hold sentinel is 2035-01-03. Return None so the entity
        # shows as unknown rather than a meaningless far-future date.
        if value.year == 2035:
            return None
        return value

    async def async_set_value(self, value: datetime) -> None:
        """Set a timed hold end time.

        Writes TIMESTAMP first, then SET_HOLD_SCHEDULE after a 0.5s delay.
        Combined writes cause ecobee to ignore TIMESTAMP and default to a
        permanent hold (it appears to process SET_HOLD_SCHEDULE first).

        Format: ecobee appends a trailing 'T' to its own ISO-8601 timestamps;
        we mirror that on writes so the format round-trips correctly.

        Mode defaults to the current comfort profile (home/sleep/away = 0/1/2).
        Temp hold (mode 3) is clamped to home (0) as a safe default.
        """
        raw_mode: int = self.service.value(CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE)
        mode = raw_mode if raw_mode in (0, 1, 2) else 0
        ts = value.isoformat() + "T"
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME: ts}
        )
        await asyncio.sleep(0.5)
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: mode}
        )


# ── Hold active binary sensor ──────────────────────────────────────────────────

class EcobeeHoldActiveBinarySensor(CharacteristicEntity, BinarySensorEntity):
    """Binary sensor that is True when an ecobee hold is active.

    Derived from VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME: the characteristic
    has a non-empty value whenever a hold (timed or permanent) is active.
    Registered from binary_sensor.py alongside EcobeeHoldUntilDatetime from
    datetime.py — both factories use the same char but return False so the
    char is not claimed exclusively.
    """

    def __init__(self, accessory, devinfo: ConfigType, char: Characteristic) -> None:
        """Initialise with a unique_id distinct from the datetime entity."""
        super().__init__(accessory, devinfo, char)
        self._attr_unique_id = f"{self._attr_unique_id}_hold_active"

    @property
    def name(self) -> str:
        """Return the entity name."""
        return f"{self.accessory.name} Hold Active"

    @property
    def available(self) -> bool:
        """Return True when the accessory is reachable."""
        return self._accessory.available

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME]

    @property
    def is_on(self) -> bool:
        """Return True when a hold is active (timed or permanent)."""
        return bool(self._char.value)


# ── Fan override ───────────────────────────────────────────────────────────────

class EcobeeFanEntity(CharacteristicEntity, FanEntity):
    """Ecobee fan continuous-run override.

    Wraps VENDOR_ECOBEE_FAN_WRITE_SPEED:
      0   = auto (releases hold, thermostat schedule controls the fan)
      100 = fan-on hold (run continuously regardless of HVAC call)

    Intermediate values (5-95) do not trigger a hold on the ecobee, so
    the entity is treated as binary: turn_on → 100, turn_off → 0.
    The fan may still run when off if heating/cooling is active.
    """

    _attr_translation_key = "ecobee_fan"
    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED]

    @property
    def is_on(self) -> bool:
        """Return True when a fan-on hold is active."""
        return self._char.value == 100

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        """Activate a fan-on hold (100 %)."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED: 100}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set fan speed to 0 (auto — thermostat schedule controls the fan).

        Note: this does NOT call CLEAR_HOLD, so any active temperature or
        mode hold is preserved. Use the Clear Hold button to fully resume
        the thermostat schedule.
        """
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED: 0}
        )
