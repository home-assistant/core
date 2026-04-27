"""Entity representing a Sonos Alarm."""

from __future__ import annotations

import datetime
import logging
from typing import Any, cast

from soco.alarms import Alarm
from soco.exceptions import SoCoSlaveException, SoCoUPnPException

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import ATTR_TIME, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .alarms import SonosAlarms
from .const import (
    ATTR_SPEECH_ENHANCEMENT_ENABLED,
    DOMAIN,
    MODEL_SONOS_ARC_ULTRA,
    SONOS_ALARMS_UPDATED,
    SONOS_CREATE_ALARM,
    SONOS_CREATE_SWITCHES,
    SOURCE_TV,
)
from .entity import SonosEntity, SonosPollingEntity
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"
ATTR_ID = "alarm_id"
ATTR_PLAY_MODE = "play_mode"
ATTR_RECURRENCE = "recurrence"
ATTR_SCHEDULED_TODAY = "scheduled_today"
ATTR_VOLUME = "volume"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"

ATTR_CROSSFADE = "cross_fade"
ATTR_LOUDNESS = "loudness"
ATTR_MUSIC_PLAYBACK_FULL_VOLUME = "surround_mode"
ATTR_NIGHT_SOUND = "night_mode"
ATTR_SPEECH_ENHANCEMENT = "dialog_level"
ATTR_STATUS_LIGHT = "status_light"
ATTR_SUB_ENABLED = "sub_enabled"
ATTR_SURROUND_ENABLED = "surround_enabled"
ATTR_TOUCH_CONTROLS = "buttons_enabled"
ATTR_TV_AUTOPLAY = "tv_autoplay"
ATTR_TV_UNGROUP_AUTOPLAY = "ungroup_on_autoplay"

ALL_FEATURES = (
    ATTR_TOUCH_CONTROLS,
    ATTR_CROSSFADE,
    ATTR_LOUDNESS,
    ATTR_MUSIC_PLAYBACK_FULL_VOLUME,
    ATTR_NIGHT_SOUND,
    ATTR_SPEECH_ENHANCEMENT,
    ATTR_SUB_ENABLED,
    ATTR_SURROUND_ENABLED,
    ATTR_STATUS_LIGHT,
)
ALL_SUBST_FEATURES = (ATTR_SPEECH_ENHANCEMENT_ENABLED,)

COORDINATOR_FEATURES = ATTR_CROSSFADE

POLL_REQUIRED = (
    ATTR_TOUCH_CONTROLS,
    ATTR_STATUS_LIGHT,
)

WEEKEND_DAYS = (0, 6)

_TV_SOURCE = (("Source", SOURCE_TV),)

# Mapping of model names to feature attributes that need to be substituted.
# This is used to handle differences in attributes across Sonos models.
MODEL_FEATURE_SUBSTITUTIONS: dict[str, dict[str, str]] = {
    MODEL_SONOS_ARC_ULTRA: {
        ATTR_SPEECH_ENHANCEMENT: ATTR_SPEECH_ENHANCEMENT_ENABLED,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""

    async def _async_create_alarms(speaker: SonosSpeaker, alarm_ids: list[str]) -> None:
        entities = []
        created_alarms = config_entry.runtime_data.alarms[
            speaker.household_id
        ].created_alarm_ids
        for alarm_id in alarm_ids:
            if alarm_id in created_alarms:
                continue
            _LOGGER.debug("Creating alarm %s on %s", alarm_id, speaker.zone_name)
            created_alarms.add(alarm_id)
            entities.append(SonosAlarmEntity(alarm_id, speaker, config_entry))
        async_add_entities(entities)

    def available_soco_attributes(speaker: SonosSpeaker) -> list[str]:
        features = []
        for feature_type in ALL_SUBST_FEATURES:
            try:
                if (state := getattr(speaker.soco, feature_type, None)) is not None:
                    setattr(speaker, feature_type, state)
            except SoCoSlaveException:
                pass

        for feature_type in ALL_FEATURES:
            try:
                if (state := getattr(speaker.soco, feature_type, None)) is not None:
                    setattr(speaker, feature_type, state)
                    features.append(feature_type)
            except SoCoSlaveException:
                features.append(feature_type)
        return features

    def _get_tv_autoplay_state(speaker: SonosSpeaker) -> str | None:
        """Return initial TV autoplay RoomUUID, or None if not supported."""
        try:
            result = speaker.soco.deviceProperties.GetAutoplayRoomUUID(_TV_SOURCE)
        except (SoCoUPnPException, SoCoSlaveException, OSError) as err:
            _LOGGER.debug(
                "Unable to read %s state for %s: %s",
                ATTR_TV_AUTOPLAY,
                speaker.zone_name,
                err,
            )
            return None
        return result.get("RoomUUID")

    def _get_tv_ungroup_autoplay_state(speaker: SonosSpeaker) -> bool | None:
        """Return initial TV ungroup-on-autoplay state, or None if not supported."""
        try:
            result = speaker.soco.deviceProperties.GetAutoplayLinkedZones(_TV_SOURCE)
        except (SoCoUPnPException, SoCoSlaveException, OSError) as err:
            _LOGGER.debug(
                "Unable to read %s state for %s: %s",
                ATTR_TV_UNGROUP_AUTOPLAY,
                speaker.zone_name,
                err,
            )
            return None
        # IncludeLinkedZones=0 means "don't include linked zones" = ungroup = ON
        return result.get("IncludeLinkedZones") == "0"

    def _get_switch_state(
        speaker: SonosSpeaker,
    ) -> tuple[list[str], str | None, bool | None]:
        """Return all switch state needed for entity creation in a single executor call."""
        return (
            available_soco_attributes(speaker),
            _get_tv_autoplay_state(speaker),
            _get_tv_ungroup_autoplay_state(speaker),
        )

    async def _async_create_switches(speaker: SonosSpeaker) -> None:
        entities: list[SonosPollingEntity] = []
        (
            available_features,
            initial_autoplay,
            initial_ungroup,
        ) = await hass.async_add_executor_job(_get_switch_state, speaker)
        for feature_type in available_features:
            attribute_key = MODEL_FEATURE_SUBSTITUTIONS.get(
                speaker.model_name.upper(), {}
            ).get(feature_type, feature_type)
            _LOGGER.debug(
                "Creating %s switch on %s attribute %s",
                feature_type,
                speaker.zone_name,
                attribute_key,
            )
            entities.append(
                SonosSwitchEntity(
                    feature_type=feature_type,
                    attribute_key=attribute_key,
                    speaker=speaker,
                    config_entry=config_entry,
                )
            )

        if initial_autoplay is not None:
            speaker.tv_autoplay = initial_autoplay
            _LOGGER.debug(
                "Creating %s switch on %s",
                ATTR_TV_AUTOPLAY,
                speaker.zone_name,
            )
            entities.append(
                SonosTVAutoplaySwitchEntity(speaker=speaker, config_entry=config_entry)
            )

        if initial_ungroup is not None:
            speaker.tv_ungroup_autoplay = initial_ungroup
            _LOGGER.debug(
                "Creating %s switch on %s",
                ATTR_TV_UNGROUP_AUTOPLAY,
                speaker.zone_name,
            )
            entities.append(
                SonosTVUngroupAutoplaySwitchEntity(
                    speaker=speaker, config_entry=config_entry
                )
            )

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_ALARM, _async_create_alarms)
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_SWITCHES, _async_create_switches)
    )


class SonosSwitchEntity(SonosPollingEntity, SwitchEntity):
    """Representation of a Sonos feature switch."""

    def __init__(
        self,
        feature_type: str,
        attribute_key: str,
        speaker: SonosSpeaker,
        config_entry: SonosConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(speaker, config_entry)
        self.attribute_key = attribute_key
        self.needs_coordinator = feature_type in COORDINATOR_FEATURES
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_translation_key = feature_type
        self._attr_unique_id = f"{speaker.soco.uid}-{feature_type}"

        if feature_type in POLL_REQUIRED:
            self._attr_entity_registry_enabled_default = False
            self._attr_should_poll = True

    async def _async_fallback_poll(self) -> None:
        """Handle polling for subscription-based switches when subscription fails."""
        if not self.should_poll:
            await self.hass.async_add_executor_job(self.poll_state)

    @soco_error()
    def poll_state(self) -> None:
        """Poll the current state of the switch."""
        state = getattr(self.soco, self.attribute_key)
        setattr(self.speaker, self.attribute_key, state)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.needs_coordinator and not self.speaker.is_coordinator:
            return cast(bool, getattr(self.speaker.coordinator, self.attribute_key))
        return cast(bool, getattr(self.speaker, self.attribute_key))

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.send_command(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.send_command(False)

    @soco_error()
    def send_command(self, enable: bool) -> None:
        """Enable or disable the feature on the device."""
        if self.needs_coordinator:
            soco = self.soco.group.coordinator
        else:
            soco = self.soco
        try:
            setattr(soco, self.attribute_key, enable)
        except SoCoUPnPException as exc:
            _LOGGER.warning("Could not toggle %s: %s", self.entity_id, exc)


class SonosTVAutoplaySwitchEntity(SonosPollingEntity, SwitchEntity):
    """Representation of a Sonos TV autoplay switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = ATTR_TV_AUTOPLAY
    _attr_should_poll = True

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{speaker.soco.uid}-{ATTR_TV_AUTOPLAY}"

    @soco_error()
    def poll_state(self) -> None:
        """Poll the current TV autoplay state from the device."""
        result = self.soco.deviceProperties.GetAutoplayRoomUUID(_TV_SOURCE)
        self.speaker.tv_autoplay = result.get("RoomUUID")

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.speaker.tv_autoplay is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if TV autoplay is enabled."""
        if self.speaker.tv_autoplay is None:
            return None
        return bool(self.speaker.tv_autoplay)

    def turn_on(self, **kwargs: Any) -> None:
        """Enable TV autoplay."""
        self._send_command(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Disable TV autoplay."""
        self._send_command(False)

    @soco_error()
    def _send_command(self, enable: bool) -> None:
        """Enable or disable TV autoplay on the device."""
        room_uuid = self.soco.uid if enable else ""
        try:
            self.soco.deviceProperties.SetAutoplayRoomUUID(
                [("RoomUUID", room_uuid), *_TV_SOURCE]
            )
        except SoCoUPnPException as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="toggle_failed",
                translation_placeholders={"entity_id": self.entity_id},
            ) from exc
        self.poll_state()
        # Refresh ungroup state: the device may change it as a side effect
        # (e.g. disabling TV autoplay automatically disables ungroup on autoplay).
        try:
            result = self.soco.deviceProperties.GetAutoplayLinkedZones(_TV_SOURCE)
            self.speaker.tv_ungroup_autoplay = result.get("IncludeLinkedZones") == "0"
        except SoCoUPnPException as exc:
            _LOGGER.debug(
                "Could not refresh %s state: %s", ATTR_TV_UNGROUP_AUTOPLAY, exc
            )
        self.speaker.write_entity_states()


class SonosTVUngroupAutoplaySwitchEntity(SonosPollingEntity, SwitchEntity):
    """Representation of a Sonos TV ungroup-on-autoplay switch.

    When enabled, the speaker leaves its group when it detects TV audio and
    takes over playback alone. The device manages the dependency with TV autoplay
    and will reflect the correct state via polling.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = ATTR_TV_UNGROUP_AUTOPLAY
    _attr_should_poll = True

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{speaker.soco.uid}-{ATTR_TV_UNGROUP_AUTOPLAY}"

    @soco_error()
    def poll_state(self) -> None:
        """Poll the current ungroup-on-autoplay state from the device."""
        result = self.soco.deviceProperties.GetAutoplayLinkedZones(_TV_SOURCE)
        linked_zones = result.get("IncludeLinkedZones")
        if linked_zones is None:
            self.speaker.tv_ungroup_autoplay = None
            return
        # IncludeLinkedZones=0 means "don't include linked zones" = ungroup = ON
        self.speaker.tv_ungroup_autoplay = linked_zones == "0"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.speaker.tv_ungroup_autoplay is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if ungroup on autoplay is enabled."""
        return self.speaker.tv_ungroup_autoplay

    def turn_on(self, **kwargs: Any) -> None:
        """Enable ungroup on autoplay."""
        self._send_command(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Disable ungroup on autoplay."""
        self._send_command(False)

    @soco_error()
    def _send_command(self, enable: bool) -> None:
        """Enable or disable ungroup on autoplay on the device."""
        try:
            self.soco.deviceProperties.SetAutoplayLinkedZones(
                # enable=True (ungroup) → IncludeLinkedZones=0 (don't include linked zones)
                [("IncludeLinkedZones", "0" if enable else "1"), *_TV_SOURCE]
            )
        except SoCoUPnPException as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="toggle_failed",
                translation_placeholders={"entity_id": self.entity_id},
            ) from exc
        self.poll_state()
        self.speaker.write_entity_states()


class SonosAlarmEntity(SonosEntity, SwitchEntity):
    """Representation of a Sonos Alarm entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:alarm"

    def __init__(
        self, alarm_id: str, speaker: SonosSpeaker, config_entry: SonosConfigEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"alarm-{speaker.household_id}:{alarm_id}"
        self.alarm_id = alarm_id
        self.household_id = speaker.household_id
        self.entity_id = ENTITY_ID_FORMAT.format(f"sonos_alarm_{self.alarm_id}")

    async def async_added_to_hass(self) -> None:
        """Handle switch setup when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_ALARMS_UPDATED}-{self.household_id}",
                self.async_update_state,
            )
        )

        async def async_write_state_daily(now: datetime.datetime) -> None:
            """Update alarm state attributes each calendar day."""
            _LOGGER.debug("Updating state attributes for %s", self.name)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(
                self.hass, async_write_state_daily, hour=0, minute=0, second=0
            )
        )

    @property
    def alarm(self) -> Alarm:
        """Return the alarm instance."""
        return self.config_entry.runtime_data.alarms[self.household_id].get(
            self.alarm_id
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return (
            f"{self.alarm.recurrence.capitalize()} alarm"
            f" {str(self.alarm.start_time)[:5]}"
        )

    async def _async_fallback_poll(self) -> None:
        """Call the central alarm polling method."""
        alarms: SonosAlarms = self.config_entry.runtime_data.alarms[self.household_id]
        assert alarms.async_poll
        await alarms.async_poll()

    @callback
    def async_check_if_available(self) -> bool:
        """Check if alarm exists and remove alarm entity if not available."""
        if self.alarm:
            return True

        _LOGGER.debug("%s has been deleted", self.entity_id)

        entity_registry = er.async_get(self.hass)
        if entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)

        return False

    async def async_update_state(self) -> None:
        """Poll the device for the current state."""
        if not self.async_check_if_available():
            return

        if self.speaker.soco.uid != self.alarm.zone.uid:
            speaker = self.config_entry.runtime_data.discovered.get(self.alarm.zone.uid)
            assert speaker
            self.speaker = speaker
            if self.speaker is None:
                raise RuntimeError(
                    "No configured Sonos speaker has been found to match the alarm."
                )

            self._async_update_device()

        self.async_write_ha_state()

    @callback
    def _async_update_device(self) -> None:
        """Update the device, since this alarm moved to a different player."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entity = entity_registry.async_get(self.entity_id)

        if entity is None:
            raise RuntimeError("Alarm has been deleted by accident.")

        new_device = device_registry.async_get_or_create(
            config_entry_id=cast(str, entity.config_entry_id),
            identifiers={(DOMAIN, self.soco.uid)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.speaker.mac_address)},
        )
        if (
            device := entity_registry.async_get(self.entity_id)
        ) and device.device_id != new_device.id:
            _LOGGER.debug("%s is moving to %s", self.entity_id, new_device.name)
            entity_registry.async_update_entity(self.entity_id, device_id=new_device.id)

    @property
    def _is_today(self) -> bool:
        """Return whether this alarm is scheduled for today."""
        recurrence = self.alarm.recurrence
        daynum = int(datetime.datetime.today().strftime("%w"))
        return (
            recurrence in ("DAILY", "ONCE")
            or (recurrence == "WEEKENDS" and daynum in WEEKEND_DAYS)
            or (recurrence == "WEEKDAYS" and daynum not in WEEKEND_DAYS)
            or (recurrence.startswith("ON_") and str(daynum) in recurrence)
        )

    @property
    def available(self) -> bool:
        """Return whether this alarm is available."""
        return (self.alarm is not None) and self.speaker.available

    @property
    def is_on(self) -> bool:
        """Return state of Sonos alarm switch."""
        return self.alarm.enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes of Sonos alarm switch."""
        return {
            ATTR_ID: str(self.alarm_id),
            ATTR_TIME: str(self.alarm.start_time),
            ATTR_DURATION: str(self.alarm.duration),
            ATTR_RECURRENCE: str(self.alarm.recurrence),
            ATTR_VOLUME: self.alarm.volume / 100,
            ATTR_PLAY_MODE: str(self.alarm.play_mode),
            ATTR_SCHEDULED_TODAY: self._is_today,
            ATTR_INCLUDE_LINKED_ZONES: self.alarm.include_linked_zones,
        }

    def turn_on(self, **kwargs: Any) -> None:
        """Turn alarm switch on."""
        self._handle_switch_on_off(turn_on=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn alarm switch off."""
        self._handle_switch_on_off(turn_on=False)

    @soco_error()
    def _handle_switch_on_off(self, turn_on: bool) -> None:
        """Handle turn on/off of alarm switch."""
        self.alarm.enabled = turn_on
        self.alarm.save()
