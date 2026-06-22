"""Support for Bosch SHC event entities."""

from __future__ import annotations

from boschshcpy import (
    SHCUniversalSwitch,
    SHCLightControl,
    SHCMotionDetector,
    SHCSession,
    SHCSmokeDetectionSystem,
    SHCSmokeDetector,
)

from homeassistant.components.event import (
    ENTITY_ID_FORMAT,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    ATTR_NAME,
)

from homeassistant.helpers.device_registry import DeviceEntry

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .entity import SHCEntity, device_excluded
from .const import (
    ATTR_LAST_TIME_TRIGGERED,
    ATTR_EVENT_TYPE,
    ATTR_EVENT_SUBTYPE,
    DATA_SESSION,
    DATA_SHC,
    DOMAIN,
    LOGGER,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BoschSHC event entities."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][entry.entry_id][DATA_SESSION]

    entities = []
    for switch_device in session.device_helper.universal_switches:
        if device_excluded(switch_device, entry.options):
            continue
        for keystate in switch_device.keystates:
            entities.append(
                UniversalSwitchEvent(
                    switch_device,
                    entry_id=entry.entry_id,
                    key_id=keystate,
                )
            )

    # Scenarios are not room devices — never filtered by device/room exclusion.
    for scenario in session.scenarios:
        entities.append(
            SHCScenarioEvent(
                scenario,
                session,
                hass,
                entry_id=entry.entry_id,
            )
        )

    # #282: Light Control II configured as a non-switching push-button emits
    # Keypad events the user can react to. Only create the entity when the
    # device actually exposes a Keypad service.
    for light_control in getattr(
        session.device_helper, "micromodule_light_controls", []
    ):
        if device_excluded(light_control, entry.options):
            continue
        if not getattr(light_control, "has_keypad", False):
            continue
        entities.append(
            LightControlButtonEvent(
                light_control,
                entry_id=entry.entry_id,
            )
        )

    for motion_detector in (
        session.device_helper.motion_detectors
        + session.device_helper.motion_detectors2
    ):
        if device_excluded(motion_detector, entry.options):
            continue
        entities.append(
            MotionDetectorEvent(
                device=motion_detector,
                entry_id=entry.entry_id,
            )
        )

    smoke_detection_system = session.device_helper.smoke_detection_system
    if smoke_detection_system and not device_excluded(
        smoke_detection_system, entry.options
    ):
        entities.append(
            SmokeDetectionSystemEvent(
                device=smoke_detection_system,
                entry_id=entry.entry_id,
            )
        )

    for smoke_detector in session.device_helper.smoke_detectors:
        if device_excluded(smoke_detector, entry.options):
            continue
        entities.append(
            SmokeDetectorEvent(
                device=smoke_detector,
                entry_id=entry.entry_id,
            )
        )

    async_add_entities(entities, True)


class UniversalSwitchEvent(SHCEntity, EventEntity):
    """Representation of a SHC UniversalSwitch Entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["PRESS_SHORT", "PRESS_LONG", "PRESS_LONG_RELEASED"]

    def __init__(self, device: SHCUniversalSwitch, entry_id: str, key_id: str) -> None:
        """Initialize the Universal Switch device."""
        super().__init__(device, entry_id)

        self._device = device
        self._key_id = key_id
        # Guard against phantom events: track the last event timestamp we fired
        # on so a battery-level long-poll that re-delivers a stale Keypad state
        # (same keyName, same eventTimestamp) does not trigger a duplicate event.
        self._last_fired_timestamp: int = -1

        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{slugify(self._device.name)}_button_{key_id.casefold()}"
        )
        self._attr_name = f"Button {key_id}"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_{key_id}"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        for service in self._device.device_services:
            if service.id == "Keypad":
                service.register_event(self._key_id, self._event_callback)

    def _event_callback(self) -> None:
        # Issue #192: The SHC sometimes delivers a Keypad service update that
        # piggybacks on a battery-level change, replaying the last stale keyName
        # and eventTimestamp without a new keypress having occurred.  Guard:
        # (1) eventtype must be a genuine button press, never None or a
        #     SWITCH_ON/SWITCH_OFF motor event; (2) eventtimestamp must have
        #     advanced since the last event we actually fired.
        event_type_raw = self._device.eventtype
        if event_type_raw is None:
            return
        event_type = event_type_raw.name
        if event_type not in ["PRESS_SHORT", "PRESS_LONG", "PRESS_LONG_RELEASED"]:
            return
        current_ts = self._device.eventtimestamp
        if current_ts == self._last_fired_timestamp:
            LOGGER.debug(
                "Skipping duplicate Keypad event for %s (ts=%s unchanged)",
                self.entity_id,
                current_ts,
            )
            return
        self._last_fired_timestamp = current_ts
        event_attributes = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_EVENT_TYPE: event_type,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
            ATTR_LAST_TIME_TRIGGERED: current_ts,
        }
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, event_type, event_attributes
        )

    @callback
    def _dispatch_event(self, event_type, event_attributes):
        """Dispatch the event on the event loop (thread-safe)."""
        try:
            self._trigger_event(event_type, event_attributes)
        except ValueError:
            LOGGER.warning(
                "Invalid event type %s for %s", event_type, self.entity_id
            )
            return
        self.schedule_update_ha_state()


class LightControlButtonEvent(SHCEntity, EventEntity):
    """Wall push-button press from a Light Control II (#282)."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [
        "PRESS_SHORT",
        "PRESS_LONG",
        "PRESS_LONG_RELEASED",
        "SWITCH_ON",
        "SWITCH_OFF",
    ]

    def __init__(self, device: SHCLightControl, entry_id: str) -> None:
        """Initialize the Light Control button event entity."""
        super().__init__(device, entry_id)
        self._device = device
        # Guard against phantom events: a Keypad update piggybacking on another
        # state change can replay the last eventTimestamp (cf. #192).
        self._last_fired_timestamp: int = -1
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{slugify(self._device.name)}_button"
        )
        self._attr_name = "Button"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_button"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        for service in self._device.device_services:
            if service.id == "Keypad":
                # Keypad events are dispatched by the reported keyName string
                # (device_service._process_events). The single-button Light
                # Control II's keyName is not HW-confirmed, so register the
                # callback under every KeyState value — whichever the device
                # reports will resolve.
                for key_state in service.KeyState:
                    service.register_event(key_state.value, self._event_callback)

    def _event_callback(self) -> None:
        event_type_raw = self._device.eventtype
        if event_type_raw is None:
            return
        event_type = event_type_raw.name
        if event_type not in self._attr_event_types:
            return
        current_ts = self._device.eventtimestamp
        if current_ts == self._last_fired_timestamp:
            return
        self._last_fired_timestamp = current_ts
        event_attributes = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_EVENT_TYPE: event_type,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
            ATTR_LAST_TIME_TRIGGERED: current_ts,
        }
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, event_type, event_attributes
        )

    @callback
    def _dispatch_event(self, event_type, event_attributes):
        """Dispatch the event on the event loop (thread-safe)."""
        try:
            self._trigger_event(event_type, event_attributes)
        except ValueError:
            LOGGER.warning(
                "Invalid event type %s for %s", event_type, self.entity_id
            )
            return
        self.schedule_update_ha_state()


class SHCScenarioEvent(EventEntity):
    """Representation of a SHC Scenario Entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["SCENARIO"]
    _attr_has_entity_name = True

    def __init__(self, scenario, session, hass, entry_id: str) -> None:
        """Initialize the Scenario device."""

        self._scenario = scenario
        self._session = session

        self.entity_id = ENTITY_ID_FORMAT.format(
            f"scenario_{slugify(self._scenario.name)}"
        )
        # Scenario name is the feature label; HA prepends the device (controller) name.
        self._attr_name = f"{self._scenario.name} Scenario"
        self._attr_unique_id = f"{session.information.unique_id}_{self._scenario.id}"

        self._shc: DeviceEntry = hass.data[DOMAIN][entry_id][DATA_SHC]

    @property
    def device_name(self):
        """Name of the device."""
        return self._shc.name

    @property
    def device_id(self):
        """Device id of the entity."""
        return self._shc.id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": self._shc.identifiers,
            "name": self._shc.name,
            "manufacturer": self._shc.manufacturer,
            "model": self._shc.model,
        }

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        self._session.subscribe_scenario_callback(
            self._scenario.id, self._event_callback
        )

    def _event_callback(self, event_data) -> None:
        event_type = "SCENARIO"
        event_attributes = {
            ATTR_EVENT_TYPE: event_type,
            ATTR_ID: event_data["id"],
            ATTR_NAME: event_data["name"],
            ATTR_LAST_TIME_TRIGGERED: event_data["lastTimeTriggered"],
        }
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, event_type, event_attributes
        )

    @callback
    def _dispatch_event(self, event_type, event_attributes):
        """Dispatch the event on the event loop (thread-safe)."""
        self._trigger_event(event_type, event_attributes)
        self.schedule_update_ha_state()


class MotionDetectorEvent(SHCEntity, EventEntity):
    """Representation of a SHC MotionDetector Entity."""

    _attr_device_class = EventDeviceClass.MOTION
    _attr_event_types = ["MOTION"]

    def __init__(self, device: SHCMotionDetector, entry_id: str) -> None:
        """Initialize the Universal Switch device."""
        super().__init__(device, entry_id)
        self._device = device

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        for service in self._device.device_services:
            if service.id == "LatestMotion":
                service.register_event(self._device.id, self._event_callback)

    def _event_callback(self) -> None:
        event_type = "MOTION"
        event_attributes = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_EVENT_TYPE: event_type,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
            ATTR_LAST_TIME_TRIGGERED: self._device.latestmotion,
        }
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, event_type, event_attributes
        )

    @callback
    def _dispatch_event(self, event_type, event_attributes):
        """Dispatch the event on the event loop (thread-safe)."""
        self._trigger_event(event_type, event_attributes)
        self.schedule_update_ha_state()


class SmokeDetectionSystemEvent(SHCEntity, EventEntity):
    """Representation of a SHC smoke detection system event entity."""

    _attr_event_types = ["ALARM"]

    def __init__(
        self,
        device: SHCSmokeDetectionSystem,
        entry_id: str,
    ):
        """Initialize the smoke detection system device."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        for service in self._device.device_services:
            if service.id == "SurveillanceAlarm":
                service.register_event(self._device.id, self._event_callback)

    def _event_callback(self) -> None:
        event_type = "ALARM"
        event_attributes = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_EVENT_TYPE: event_type,
            ATTR_EVENT_SUBTYPE: self._device.alarm.name,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
        }
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, event_type, event_attributes
        )

    @callback
    def _dispatch_event(self, event_type, event_attributes):
        """Dispatch the event on the event loop (thread-safe)."""
        self._trigger_event(event_type, event_attributes)
        self.schedule_update_ha_state()


class SmokeDetectorEvent(SHCEntity, EventEntity):
    """Representation of a SHC smoke detector event entity."""

    _attr_event_types = ["ALARM"]

    def __init__(
        self,
        device: SHCSmokeDetector,
        entry_id: str,
    ):
        """Initialize the smoke detection system device."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        for service in self._device.device_services:
            if service.id == "Alarm":
                service.register_event(self._device.id, self._event_callback)

    def _event_callback(self) -> None:
        event_type = "ALARM"
        event_attributes = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_EVENT_TYPE: event_type,
            ATTR_EVENT_SUBTYPE: self._device.alarmstate.name,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
        }
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, event_type, event_attributes
        )

    @callback
    def _dispatch_event(self, event_type, event_attributes):
        """Dispatch the event on the event loop (thread-safe)."""
        self._trigger_event(event_type, event_attributes)
        self.schedule_update_ha_state()
