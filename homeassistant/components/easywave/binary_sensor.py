"""Binary sensor platform for Easywave type-2 channel transmitters.

Type-2 transmitters map pairs of buttons to an on/off or open/closed channel
state.  Using BinarySensorEntity (instead of SensorEntity(ENUM)) is the correct
HA semantic: the binary_sensor platform auto-generates properly labelled device
triggers ("turned on" / "turned off", "opened" / "not opened") via
binary_sensor/device_trigger.py, removing the need for custom state_* trigger
types in the integration's device_trigger.py.
"""

from dataclasses import dataclass
from typing import Any, Self

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import EasywaveConfigEntry, get_devices
from .const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_OPERATING_TYPE,
    CONF_USAGE_TYPE,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_USAGE_COVER,
)
from .entity import EasywaveDeviceEntry, EasywaveTransmitterEntity


@dataclass
class _ChannelRestoreData(ExtraStoredData):
    """Serialisable extra data for channel binary sensor state restore."""

    is_on: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {"is_on": self.is_on}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self | None:
        try:
            return cls(is_on=data["is_on"])
        except KeyError:
            return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave channel binary sensor entities from transmitter subentries.

    Note: Type-2 transmitters with TRANSMITTER_USAGE_COVER are handled by the
    cover platform (EasywaveTransmitterChannelCover) instead of binary sensors.
    """
    for subentry in get_devices(entry):
        if subentry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_TRANSMITTER:
            continue

        operating_type = str(subentry.data.get(CONF_OPERATING_TYPE, "1"))
        if operating_type != "2":
            continue

        # Skip cover-type transmitters - they are handled by cover.py
        if subentry.data.get(CONF_USAGE_TYPE) == TRANSMITTER_USAGE_COVER:
            continue

        button_count: int = min(subentry.data.get(CONF_BUTTON_COUNT, 4), 4)

        if button_count <= 2:
            entities: list[EasywaveChannelBinarySensor] = [
                EasywaveChannelBinarySensor(
                    entry,
                    subentry,
                    uid_suffix="switch",
                    translation_key="transmitter_switch",
                    button_map={0: True, 1: False},
                )
            ]
        else:
            entities = []
            for suffix, ch_map in (
                ("ab", {0: True, 1: False}),
                ("cd", {2: True, 3: False}),
            ):
                entities.append(
                    EasywaveChannelBinarySensor(
                        entry,
                        subentry,
                        uid_suffix=f"switch_{suffix}",
                        translation_key=f"transmitter_switch_{suffix}",
                        button_map=ch_map,
                    )
                )

        async_add_entities(entities)


class EasywaveChannelBinarySensor(
    EasywaveTransmitterEntity, BinarySensorEntity, RestoreEntity
):
    """Binary sensor for a type-2 transmitter channel (switch on/off state).

    Switch channels use no special device_class (auto-triggers: "turned on" /
    "turned off"). State changes are driven by button press telegrams; releases
    are ignored since the channel state is latching.
    """

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        subentry: EasywaveDeviceEntry,
        uid_suffix: str,
        translation_key: str,
        button_map: dict[int, bool],
    ) -> None:
        """Initialize the channel binary sensor."""
        super().__init__(entry, subentry, uid_suffix)
        self._attr_translation_key = translation_key
        self._button_map = button_map
        self._attr_is_on: bool | None = None

    @property
    def extra_restore_state_data(self) -> _ChannelRestoreData:
        """Return is_on as extra data so it survives unavailable states at shutdown."""
        return _ChannelRestoreData(is_on=self._attr_is_on)

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator, register for telegram dispatch, and restore state."""
        # Restore last known state before setting up listeners.
        if (extra := await self.async_get_last_extra_data()) is not None:
            data = _ChannelRestoreData.from_dict(extra.as_dict())
            if data is not None and data.is_on is not None:
                self._attr_is_on = data.is_on
        elif (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in ("on", "off"):
                self._attr_is_on = last_state.state == "on"

        await super().async_added_to_hass()

        if self._attr_is_on is not None:
            self.async_write_ha_state()

    @callback
    def handle_telegram(self, info_type: int, button: int) -> None:
        """Update state on button press; ignore releases."""
        if info_type != 0x01:
            return
        new_on = self._button_map.get(button)
        if new_on is None:
            return
        if self._attr_is_on != new_on:
            self._attr_is_on = new_on
            self.async_write_ha_state()
