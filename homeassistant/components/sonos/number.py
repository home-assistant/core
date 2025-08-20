"""Entity representing a Sonos number control."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import cast

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SONOS_CREATE_LEVELS, SONOS_SPEAKER_ACTIVITY, SONOS_STATE_UPDATED
from .entity import SonosEntity
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker

LEVEL_TYPES = {
    "audio_delay": (0, 5),
    "bass": (-10, 10),
    "balance": (-100, 100),
    "treble": (-10, 10),
    "sub_crossover": (50, 110),
    "sub_gain": (-15, 15),
    "surround_level": (-15, 15),
    "music_surround_level": (-15, 15),
}

type SocoFeatures = list[tuple[str, tuple[int, int]]]

_LOGGER = logging.getLogger(__name__)


def _balance_to_number(state: tuple[int, int]) -> float:
    """Represent a balance measure returned by SoCo as a number.

    SoCo returns a pair of volumes, one for the left side and one
    for the right side. When the two are equal, sound is centered;
    HA will show that as 0. When the left side is louder, HA will
    show a negative value, and a positive value means the right
    side is louder. Maximum absolute value is 100, which means only
    one side produces sound at all.
    """
    left, right = state
    return (right - left) * 100 // max(right, left)


def _balance_from_number(value: float) -> tuple[int, int]:
    """Convert a balance value from -100 to 100 into SoCo format.

    0 becomes (100, 100), fully enabling both sides. Note that
    the master volume control is separate, so this does not
    turn up the speakers to maximum volume. Negative values
    reduce the volume of the right side, and positive values
    reduce the volume of the left side. -100 becomes (100, 0),
    fully muting the right side, and +100 becomes (0, 100),
    muting the left side.
    """
    left = min(100, 100 - int(value))
    right = min(100, int(value) + 100)
    return left, right


LEVEL_TO_NUMBER = {"balance": _balance_to_number}
LEVEL_FROM_NUMBER = {"balance": _balance_from_number}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sonos number platform from a config entry."""

    def available_soco_attributes(speaker: SonosSpeaker) -> SocoFeatures:
        features: SocoFeatures = []
        for level_type, valid_range in LEVEL_TYPES.items():
            if (state := getattr(speaker.soco, level_type, None)) is not None:
                setattr(speaker, level_type, state)
                features.append((level_type, valid_range))
        return features

    async def _async_create_entities(speaker: SonosSpeaker) -> None:
        entities: list[NumberEntity] = []

        available_features = await hass.async_add_executor_job(
            available_soco_attributes, speaker
        )

        # Standard SoCo-backed level controls
        for level_type, valid_range in available_features:
            _LOGGER.debug(
                "Creating %s number control on %s", level_type, speaker.zone_name
            )
            entities.append(
                SonosLevelEntity(speaker, config_entry, level_type, valid_range)
            )

        # Group volume slider (0.0–1.0)
        _LOGGER.debug("Creating group_volume number control on %s", speaker.zone_name)
        entities.append(SonosGroupVolumeEntity(speaker, config_entry))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_LEVELS, _async_create_entities)
    )


class SonosLevelEntity(SonosEntity, NumberEntity):
    """Representation of a Sonos level entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        speaker: SonosSpeaker,
        config_entry: SonosConfigEntry,
        level_type: str,
        valid_range: tuple[int, int],
    ) -> None:
        """Initialize the level entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-{level_type}"
        self._attr_translation_key = level_type
        self.level_type = level_type
        self._attr_native_min_value, self._attr_native_max_value = valid_range

    async def _async_fallback_poll(self) -> None:
        """Poll the value if subscriptions are not working."""
        await self.hass.async_add_executor_job(self.poll_state)

    @soco_error()
    def poll_state(self) -> None:
        """Poll the device for the current state."""
        state = getattr(self.soco, self.level_type)
        setattr(self.speaker, self.level_type, state)

    @soco_error()
    def set_native_value(self, value: float) -> None:
        """Set a new value."""
        from_number = LEVEL_FROM_NUMBER.get(self.level_type, int)
        setattr(self.soco, self.level_type, from_number(value))

    @property
    def native_value(self) -> float:
        """Return the current value."""
        to_number = LEVEL_TO_NUMBER.get(self.level_type, int)
        return cast(float, to_number(getattr(self.speaker, self.level_type)))


class SonosGroupVolumeEntity(SonosEntity, NumberEntity):
    """Group volume control (0.0–1.0) for the Sonos group of this player."""

    _attr_translation_key = "group_volume"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.01
    _attr_mode = NumberMode.SLIDER

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the Sonos group volume number entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-group_volume"
        self._cached: float | None = None
        self._coord_uid: str | None = None
        self._unsub_coord: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        """Available whenever the player is online."""
        return bool(self.speaker.available)

    # ---------- Reading / writing ----------

    @property
    def native_value(self) -> float | None:
        """Return the cached group volume (0.0–1.0)."""
        return self._cached

    @soco_error()
    def set_native_value(self, value: float) -> None:
        """Set the group volume (0.0–1.0)."""
        level = max(0.0, min(1.0, float(value)))
        self.soco.group.volume = int(round(level * 100))
        self._cached = level
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    async def _async_fallback_poll(self) -> None:
        """Poll if subscriptions aren’t working."""
        await self._async_refresh_from_device(write=True)

    async def _async_refresh_from_device(self, write: bool = False) -> None:
        """Fetch current group volume from SoCo."""

        def _get() -> int | None:
            try:
                return self.soco.group.volume
            except Exception:  # noqa: BLE001
                return None

        gv = await self.hass.async_add_executor_job(_get)
        self._cached = gv / 100.0 if isinstance(gv, int) else None
        if write:
            self.async_write_ha_state()

    # ---------- Push wiring for responsiveness ----------

    async def async_added_to_hass(self) -> None:
        """Subscribe to signals for live updates with minimal polling."""
        await super().async_added_to_hass()

        # Track current coordinator and listen for regrouping on THIS speaker only.
        self._coord_uid = (self.speaker.coordinator or self.speaker).uid
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_SPEAKER_ACTIVITY}-{self.soco.uid}",
                self._on_local_activity,
            )
        )
        # Listen to STATE_UPDATED from the current coordinator (volume/mute/transport).
        self._bind_coordinator_state(self._coord_uid)

        # Initial read
        await self._async_refresh_from_device(write=True)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when the entity is removed."""
        if self._unsub_coord is not None:
            self._unsub_coord()
            self._unsub_coord = None
        await super().async_will_remove_from_hass()

    def _bind_coordinator_state(self, coord_uid: str) -> None:
        """(Re)bind a single STATE_UPDATED listener for the given coordinator."""
        if self._unsub_coord is not None:
            self._unsub_coord()
            self._unsub_coord = None
        self._unsub_coord = async_dispatcher_connect(
            self.hass,
            f"{SONOS_STATE_UPDATED}-{coord_uid}",
            self._on_coord_state_updated,
        )
        self.async_on_remove(self._unsub_coord)

    @callback
    def _on_coord_state_updated(self, *_: object) -> None:
        """Coordinator state changed — refresh once."""
        self.hass.create_task(self._async_refresh_from_device(write=True))

    @callback
    def _on_local_activity(self, *_: object) -> None:
        """Local speaker activity — only rebind if coordinator changed."""
        new_coord_uid = (self.speaker.coordinator or self.speaker).uid
        if new_coord_uid != self._coord_uid:
            self._coord_uid = new_coord_uid
            self._bind_coordinator_state(new_coord_uid)
            self.hass.create_task(self._async_refresh_from_device(write=True))
