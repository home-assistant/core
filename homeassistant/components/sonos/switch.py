"""Entity representing a Sonos Alarm."""
from __future__ import annotations

import datetime
import logging

from soco.exceptions import SoCoException, SoCoSlaveException, SoCoUPnPException

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import ATTR_TIME, ENTITY_CATEGORY_CONFIG
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DATA_SONOS,
    DOMAIN as SONOS_DOMAIN,
    SONOS_ALARMS_UPDATED,
    SONOS_CREATE_ALARM,
    SONOS_CREATE_SWITCHES,
)
from .entity import SonosEntity
from .exception import SpeakerUnavailable
from .helpers import soco_error
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
ATTR_NIGHT_SOUND = "night_mode"
ATTR_SPEECH_ENHANCEMENT = "dialog_mode"
ATTR_STATUS_LIGHT = "status_light"
ATTR_TOUCH_CONTROLS = "buttons_enabled"

ALL_FEATURES = (
    ATTR_TOUCH_CONTROLS,
    ATTR_CROSSFADE,
    ATTR_NIGHT_SOUND,
    ATTR_SPEECH_ENHANCEMENT,
    ATTR_STATUS_LIGHT,
)

COORDINATOR_FEATURES = ATTR_CROSSFADE

POLL_REQUIRED = (
    ATTR_TOUCH_CONTROLS,
    ATTR_STATUS_LIGHT,
)

FRIENDLY_NAMES = {
    ATTR_CROSSFADE: "Crossfade",
    ATTR_NIGHT_SOUND: "Night Sound",
    ATTR_SPEECH_ENHANCEMENT: "Speech Enhancement",
    ATTR_STATUS_LIGHT: "Status Light",
    ATTR_TOUCH_CONTROLS: "Touch Controls",
}

FEATURE_ICONS = {
    ATTR_NIGHT_SOUND: "mdi:chat-sleep",
    ATTR_SPEECH_ENHANCEMENT: "mdi:ear-hearing",
    ATTR_CROSSFADE: "mdi:swap-horizontal",
    ATTR_STATUS_LIGHT: "mdi:led-on",
    ATTR_TOUCH_CONTROLS: "mdi:gesture-tap",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    async def _async_create_alarms(speaker: SonosSpeaker, alarm_ids: list[str]) -> None:
        entities = []
        created_alarms = (
            hass.data[DATA_SONOS].alarms[speaker.household_id].created_alarm_ids
        )
        for alarm_id in alarm_ids:
            if alarm_id in created_alarms:
                continue
            _LOGGER.debug("Creating alarm %s on %s", alarm_id, speaker.zone_name)
            created_alarms.add(alarm_id)
            entities.append(SonosAlarmEntity(alarm_id, speaker))
        async_add_entities(entities)

    def available_soco_attributes(speaker: SonosSpeaker) -> list[tuple[str, bool]]:
        features = []
        for feature_type in ALL_FEATURES:
            try:
                if (state := getattr(speaker.soco, feature_type, None)) is not None:
                    setattr(speaker, feature_type, state)
                    features.append(feature_type)
            except SoCoSlaveException:
                features.append(feature_type)
        return features

    async def _async_create_switches(speaker: SonosSpeaker) -> None:
        entities = []
        available_features = await hass.async_add_executor_job(
            available_soco_attributes, speaker
        )
        for feature_type in available_features:
            _LOGGER.debug(
                "Creating %s switch on %s",
                FRIENDLY_NAMES[feature_type],
                speaker.zone_name,
            )
            entities.append(SonosSwitchEntity(feature_type, speaker))
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_ALARM, _async_create_alarms)
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_SWITCHES, _async_create_switches)
    )


class SonosSwitchEntity(SonosEntity, SwitchEntity):
    """Representation of a Sonos feature switch."""

    def __init__(self, feature_type: str, speaker: SonosSpeaker) -> None:
        """Initialize the switch."""
        super().__init__(speaker)
        self.feature_type = feature_type
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"sonos_{speaker.zone_name}_{FRIENDLY_NAMES[feature_type]}"
        )
        self.needs_coordinator = feature_type in COORDINATOR_FEATURES
        self._attr_entity_category = ENTITY_CATEGORY_CONFIG
        self._attr_name = f"{speaker.zone_name} {FRIENDLY_NAMES[feature_type]}"
        self._attr_unique_id = f"{speaker.soco.uid}-{feature_type}"
        self._attr_icon = FEATURE_ICONS.get(feature_type)

        if feature_type in POLL_REQUIRED:
            self._attr_entity_registry_enabled_default = False
            self._attr_should_poll = True

    async def _async_poll(self) -> None:
        """Handle polling for subscription-based switches when subscription fails."""
        if not self.should_poll:
            await self.hass.async_add_executor_job(self.update)

    @soco_error(raise_on_err=False)
    def update(self) -> None:
        """Fetch switch state if necessary."""
        if not self.available:
            raise SpeakerUnavailable

        state = getattr(self.soco, self.feature_type)
        setattr(self.speaker, self.feature_type, state)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.needs_coordinator and not self.speaker.is_coordinator:
            return getattr(self.speaker.coordinator, self.feature_type)
        return getattr(self.speaker, self.feature_type)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.send_command(True)

    def turn_off(self, **kwargs) -> None:
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
            setattr(soco, self.feature_type, enable)
        except SoCoUPnPException as exc:
            _LOGGER.warning("Could not toggle %s: %s", self.entity_id, exc)


class SonosAlarmEntity(SonosEntity, SwitchEntity):
    """Representation of a Sonos Alarm entity."""

    _attr_entity_category = ENTITY_CATEGORY_CONFIG

    def __init__(self, alarm_id: str, speaker: SonosSpeaker) -> None:
        """Initialize the switch."""
        super().__init__(speaker)

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

    @property
    def alarm(self):
        """Return the alarm instance."""
        return self.hass.data[DATA_SONOS].alarms[self.household_id].get(self.alarm_id)

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the switch."""
        return f"{SONOS_DOMAIN}-{self.alarm_id}"

    @property
    def icon(self):
        """Return icon of Sonos alarm switch."""
        return "mdi:alarm"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "{} {} Alarm {}".format(
            self.speaker.zone_name,
            self.alarm.recurrence.title(),
            str(self.alarm.start_time)[0:5],
        )

    async def _async_poll(self) -> None:
        """Call the central alarm polling method."""
        await self.hass.data[DATA_SONOS].alarms[self.household_id].async_poll()

    @callback
    def async_check_if_available(self):
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

        _LOGGER.debug("Updating alarm: %s", self.entity_id)
        if self.speaker.soco.uid != self.alarm.zone.uid:
            self.speaker = self.hass.data[DATA_SONOS].discovered.get(
                self.alarm.zone.uid
            )
            if self.speaker is None:
                raise RuntimeError(
                    "No configured Sonos speaker has been found to match the alarm."
                )

            self._async_update_device()

        self.async_write_ha_state()

    @callback
    def _async_update_device(self):
        """Update the device, since this alarm moved to a different player."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entity = entity_registry.async_get(self.entity_id)

        if entity is None:
            raise RuntimeError("Alarm has been deleted by accident.")

        entry_id = entity.config_entry_id

        new_device = device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(SONOS_DOMAIN, self.soco.uid)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.speaker.mac_address)},
        )
        if not entity_registry.async_get(self.entity_id).device_id == new_device.id:
            _LOGGER.debug("%s is moving to %s", self.entity_id, new_device.name)
            # pylint: disable=protected-access
            entity_registry._async_update_entity(
                self.entity_id, device_id=new_device.id
            )

    @property
    def _is_today(self):
        recurrence = self.alarm.recurrence
        timestr = int(datetime.datetime.today().strftime("%w"))
        return (
            bool(recurrence[:2] == "ON" and str(timestr) in recurrence)
            or bool(recurrence == "DAILY")
            or bool(recurrence == "WEEKDAYS" and int(timestr) not in [0, 7])
            or bool(recurrence == "ONCE")
            or bool(recurrence == "WEEKDAYS" and int(timestr) not in [0, 7])
            or bool(recurrence == "WEEKENDS" and int(timestr) not in range(1, 7))
        )

    @property
    def available(self) -> bool:
        """Return whether this alarm is available."""
        return (self.alarm is not None) and self.speaker.available

    @property
    def is_on(self):
        """Return state of Sonos alarm switch."""
        return self.alarm.enabled

    @property
    def extra_state_attributes(self):
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

    async def async_turn_on(self, **kwargs) -> None:
        """Turn alarm switch on."""
        await self.async_handle_switch_on_off(turn_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn alarm switch off."""
        await self.async_handle_switch_on_off(turn_on=False)

    async def async_handle_switch_on_off(self, turn_on: bool) -> None:
        """Handle turn on/off of alarm switch."""
        try:
            _LOGGER.debug("Toggling the state of %s", self.entity_id)
            self.alarm.enabled = turn_on
            await self.hass.async_add_executor_job(self.alarm.save)
        except (OSError, SoCoException, SoCoUPnPException) as exc:
            _LOGGER.error("Could not update %s: %s", self.entity_id, exc)
