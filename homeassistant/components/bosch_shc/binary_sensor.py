"""Platform for binarysensor integration."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Callable

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from boschshcpy import (
    SHCBatteryDevice,
    SHCDevice,
    SHCMotionDetector2,
    SHCSession,
    SHCShutterContact,
    SHCShutterContact2Plus,
    SHCSmokeDetectionSystem,
    SHCSmokeDetector,
    SHCWaterLeakageSensor,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_DEVICE_ID,
    ATTR_ID,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_EVENT_SUBTYPE,
    ATTR_EVENT_TYPE,
    ATTR_LAST_TIME_TRIGGERED,
    DATA_SESSION,
    DOMAIN,
    EVENT_BOSCH_SHC,
    LOGGER,
    SERVICE_SMOKEDETECTOR_ALARMSTATE,
    SERVICE_SMOKEDETECTOR_CHECK,
)
from .entity import (
    SHCEntity,
    async_get_device_id,
    async_migrate_to_new_unique_id,
    device_excluded,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC binary sensor platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    @callback
    def async_add_shuttercontact(
        device: SHCShutterContact,
    ) -> None:
        """Add Shutter Contact 2 Binary Sensor."""
        binary_sensor = ShutterContactSensor(
            device=device,
            entry_id=config_entry.entry_id,
        )
        async_add_entities([binary_sensor])

    for binary_sensor in (
        session.device_helper.shutter_contacts + session.device_helper.shutter_contacts2
    ):
        if device_excluded(binary_sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor
        )
        async_add_shuttercontact(device=binary_sensor)

    # Register listener for new binary sensors and ensure it is torn down on
    # config entry unload.  session.subscribe() appends the tuple to
    # session._subscribers but returns None, so we build the unsubscribe
    # closure ourselves.  add_update_listener is NOT used here because it
    # expects an options-update callback (hass, entry) -> None, not the SHC
    # subscriber tuple.
    _shutter_subscriber = (SHCShutterContact, async_add_shuttercontact)
    session.subscribe(_shutter_subscriber)

    def _unsubscribe_shutter():
        try:
            session._subscribers.remove(_shutter_subscriber)
        except ValueError:
            pass

    config_entry.async_on_unload(_unsubscribe_shutter)

    for binary_sensor in session.device_helper.motion_detectors:
        if device_excluded(binary_sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor
        )
        entities.append(
            MotionDetectionSensor(
                hass=hass,
                device=binary_sensor,
                entry_id=config_entry.entry_id,
            )
        )

    for binary_sensor in session.device_helper.motion_detectors2:
        if device_excluded(binary_sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor
        )
        entities.append(
            MotionDetectionSensor(
                hass=hass,
                device=binary_sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor, attr_name="Occupancy"
        )
        entities.append(
            OccupancyDetectionSensor(
                device=binary_sensor,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            TamperSensor(
                device=binary_sensor,
                entry_id=config_entry.entry_id,
            )
        )

    for binary_sensor in session.device_helper.smoke_detectors:
        if device_excluded(binary_sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor
        )
        entities.append(
            SmokeDetectorSensor(
                device=binary_sensor,
                hass=hass,
                entry_id=config_entry.entry_id,
            )
        )

    smoke_detection_system = session.device_helper.smoke_detection_system
    if smoke_detection_system and not device_excluded(
        smoke_detection_system, config_entry.options
    ):
        entities.append(
            SmokeDetectionSystemSensor(
                device=smoke_detection_system,
                hass=hass,
                entry_id=config_entry.entry_id,
            )
        )
        twinguards = session.device_helper.twinguards
        if twinguards:
            tracker = TwinguardAlarmTracker(
                session=session,
                smoke_detection_system=smoke_detection_system,
                hass=hass,
            )
            # Initial refresh (async; awaits get_messages on the loop).
            await tracker.async_refresh()

            def _cleanup_tracker():
                tracker.teardown()

            config_entry.async_on_unload(_cleanup_tracker)
            # async_listen_once returns an unsubscribe callable; register it so the
            # listener is removed on config-entry reload (prevents closure leak).
            config_entry.async_on_unload(
                hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, lambda _: tracker.teardown()
                )
            )

            for binary_sensor in twinguards:
                if device_excluded(binary_sensor, config_entry.options):
                    continue
                entities.append(
                    TwinguardSmokeAlarmSensor(
                        device=binary_sensor,
                        entry_id=config_entry.entry_id,
                        tracker=tracker,
                    )
                )

    for binary_sensor in session.device_helper.water_leakage_detectors:
        if device_excluded(binary_sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor
        )
        entities.append(
            WaterLeakageDetectorSensor(
                device=binary_sensor,
                entry_id=config_entry.entry_id,
            )
        )

    for binary_sensor in session.device_helper.shutter_contacts2:
        if device_excluded(binary_sensor, config_entry.options):
            continue
        if isinstance(binary_sensor, SHCShutterContact2Plus):
            entities.append(
                ShutterContactVibrationSensor(
                    device=binary_sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    for binary_sensor in (
        session.device_helper.motion_detectors
        + session.device_helper.motion_detectors2
        + session.device_helper.shutter_contacts
        + session.device_helper.shutter_contacts2
        + session.device_helper.smoke_detectors
        + session.device_helper.thermostats
        + session.device_helper.twinguards
        + session.device_helper.universal_switches
        + session.device_helper.wallthermostats
        + session.device_helper.roomthermostats
        + session.device_helper.water_leakage_detectors
    ):
        if device_excluded(binary_sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.BINARY_SENSOR, device=binary_sensor, attr_name="Battery"
        )
        if binary_sensor.supports_batterylevel:
            entities.append(
                BatterySensor(
                    device=binary_sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    # Room-climate "call for heat" (#205): expose RoomClimateControl.has_demand
    # as a binary_sensor so automations can see when a room is requesting heat.
    for climate in session.device_helper.climate_controls:
        if device_excluded(climate, config_entry.options):
            continue
        entities.append(
            CallForHeatSensor(
                device=climate,
                entry_id=config_entry.entry_id,
            )
        )

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SMOKEDETECTOR_CHECK,
        {},
        "async_request_smoketest",
    )
    platform.async_register_entity_service(
        SERVICE_SMOKEDETECTOR_ALARMSTATE,
        {
            vol.Required(ATTR_COMMAND): cv.string,
        },
        "async_request_alarmstate",
    )

    if entities:
        async_add_entities(entities)


class CallForHeatSensor(SHCEntity, BinarySensorEntity):
    """Room-climate 'call for heat' sensor — on when the room requests heat.

    Reads RoomClimateControl.has_demand (#205). getattr-guarded so it tolerates
    an older boschshcpy without the property (degrades to off rather than crash).
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:radiator"

    def __init__(self, device, entry_id: str) -> None:
        """Initialize a call-for-heat binary sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Call for Heat"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_callforheat"

    @property
    def is_on(self):
        """Return True when the room climate control is calling for heat."""
        return bool(getattr(self._device, "has_demand", False))


class ShutterContactSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC shutter contact sensor."""

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._device.state == SHCShutterContact.ShutterContactService.State.OPEN

    @property
    def device_class(self):
        """Return the class of this device."""
        switcher = {
            "ENTRANCE_DOOR": BinarySensorDeviceClass.DOOR,
            "REGULAR_WINDOW": BinarySensorDeviceClass.WINDOW,
            "FRENCH_WINDOW": BinarySensorDeviceClass.DOOR,
            "GENERIC": BinarySensorDeviceClass.WINDOW,
        }
        return switcher.get(self._device.device_class, BinarySensorDeviceClass.WINDOW)


class ShutterContactVibrationSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC shutter contact vibration sensor."""

    _attr_device_class = BinarySensorDeviceClass.VIBRATION

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC temperature reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Vibration"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_vibration"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.vibrationsensor
            == SHCShutterContact2Plus.VibrationSensorService.State.VIBRATION_DETECTED
        )


class MotionDetectionSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC motion detection sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, hass, device, entry_id: str):
        """Initialize the motion detection device."""
        self.hass = hass
        self._service = None
        self._cached_device_id = None
        super().__init__(device=device, entry_id=entry_id)

        for service in self._device.device_services:
            if service.id == "LatestMotion":
                self._service = service
                break

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)

    async def async_added_to_hass(self):
        """Subscribe to SHC events and cache device_id."""
        await super().async_added_to_hass()
        self._cached_device_id = await async_get_device_id(
            self.hass, self._device.id
        )
        # Subscribe AFTER device_id is cached so events never fire with
        # device_id=None during the startup window (#288-cluster).
        if self._service is not None:
            self._service.subscribe_callback(
                self._device.id + "_eventlistener", self._input_events_handler
            )

    def _input_events_handler(self):
        """Handle device input events (called from SHCPollingThread)."""
        self.hass.loop.call_soon_threadsafe(
            self.hass.bus.fire,
            EVENT_BOSCH_SHC,
            {
                ATTR_DEVICE_ID: self._cached_device_id,
                ATTR_ID: self._device.id,
                ATTR_NAME: self._device.name,
                ATTR_LAST_TIME_TRIGGERED: self._device.latestmotion,
                ATTR_EVENT_TYPE: "MOTION",
                ATTR_EVENT_SUBTYPE: "",
            },
        )

    @callback
    def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        LOGGER.debug(
            "Stopping motion detection event listener for %s", self._device.name
        )
        self._service.unsubscribe_callback(self._device.id + "_eventlistener")

    @property
    def is_on(self):
        """Return the state of the sensor."""
        try:
            latestmotion = datetime.strptime(
                self._device.latestmotion, "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            # ValueError: unparseable timestamp; TypeError: latestmotion is None.
            # The trailing literal "Z" makes strptime return a naive datetime, so
            # it must be marked UTC-aware to subtract from datetime.now(timezone.utc).
            return False

        elapsed = datetime.now(timezone.utc) - latestmotion
        if elapsed > timedelta(seconds=4 * 60):
            return False
        return True

    @property
    def should_poll(self):
        """Retrieve motion state."""
        return True

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "last_motion_detected": self._device.latestmotion,
        }


class SmokeDetectorSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC smoke detector sensor."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE

    def __init__(
        self,
        device: SHCSmokeDetector,
        hass: HomeAssistant,
        entry_id: str,
    ):
        """Initialize the smoke detector device."""
        self._hass = hass
        self._service = None
        self._cached_device_id = None
        super().__init__(device=device, entry_id=entry_id)

        for service in self._device.device_services:
            if service.id == "Alarm":
                self._service = service
                break

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)

    async def async_added_to_hass(self):
        """Subscribe to SHC events and cache device_id."""
        await super().async_added_to_hass()
        self._cached_device_id = await async_get_device_id(
            self._hass, self._device.id
        )
        # Subscribe AFTER device_id is cached so events never fire with
        # device_id=None during the startup window (#288-cluster).
        if self._service is not None:
            self._service.subscribe_callback(
                self._device.id + "_eventlistener", self._input_events_handler
            )

    def _input_events_handler(self):
        """Handle device input events (called from SHCPollingThread)."""
        self._hass.loop.call_soon_threadsafe(
            self._hass.bus.fire,
            EVENT_BOSCH_SHC,
            {
                ATTR_DEVICE_ID: self._cached_device_id,
                ATTR_ID: self._device.id,
                ATTR_NAME: self._device.name,
                ATTR_EVENT_TYPE: "ALARM",
                ATTR_EVENT_SUBTYPE: self._device.alarmstate.name,
            },
        )

    @callback
    def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        LOGGER.debug("Stopping alarm event listener for %s", self._device.name)
        self._service.unsubscribe_callback(self._device.id + "_eventlistener")

    @property
    def is_on(self):
        """Return the state of the sensor."""
        # Only PRIMARY_ALARM and SECONDARY_ALARM are smoke-related states.
        # INTRUSION_ALARM is set by the IDS (intrusion detection system) on all
        # smoke detectors when a surveillance alarm fires — it must NOT be treated
        # as a smoke event, or every detector reports smoke whenever any burglar
        # alarm triggers (issue #191).
        return self._device.alarmstate in (
            SHCSmokeDetector.AlarmService.State.PRIMARY_ALARM,
            SHCSmokeDetector.AlarmService.State.SECONDARY_ALARM,
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:smoke-detector"

    async def async_request_smoketest(self):
        """Request smokedetector test."""
        from boschshcpy.exceptions import SHCException, SHCConnectionError
        LOGGER.debug("Requesting smoke test on entity %s", self.name)
        try:
            await self._device.async_smoketest_requested()
        except (SHCException, SHCConnectionError) as err:
            raise HomeAssistantError(
                f"Smoke test request failed for {self.name}: {err}"
            ) from err

    async def async_request_alarmstate(self, command: str):
        """Request smokedetector alarm state."""
        from boschshcpy.exceptions import SHCException, SHCConnectionError

        LOGGER.debug(
            "Requesting custom alarm state %s on entity %s", command, self.name
        )
        try:
            await self._device.async_set_alarmstate(command)
        except (SHCException, SHCConnectionError) as err:
            raise HomeAssistantError(
                f"Set alarm state failed for {self.name}: {err}"
            ) from err

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            check_state = self._device.smokedetectorcheck_state.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown smokedetectorcheck_state for %s: %s", self._device.name, err
            )
            check_state = None
        try:
            alarm_state = self._device.alarmstate.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown alarmstate for %s: %s", self._device.name, err
            )
            alarm_state = None
        return {
            "smokedetectorcheck_state": check_state,
            "alarmstate": alarm_state,
        }


class WaterLeakageDetectorSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC water leakage detector sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.leakage_state
            != SHCWaterLeakageSensor.WaterLeakageSensorService.State.NO_LEAKAGE
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:water-alert"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "push_notification_state": self._device.push_notification_state.name,
            "acoustic_signal_state": self._device.acoustic_signal_state.name,
        }


class SmokeDetectionSystemSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC smoke detection system sensor."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE

    def __init__(
        self,
        device: SHCSmokeDetectionSystem,
        hass: HomeAssistant,
        entry_id: str,
    ):
        """Initialize the smoke detection system device."""
        self._hass = hass
        self._service = None
        self._cached_device_id = None
        super().__init__(device=device, entry_id=entry_id)
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"
        self._attr_name = None

        for service in self._device.device_services:
            if service.id == "SurveillanceAlarm":
                self._service = service
                break

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)

    async def async_added_to_hass(self):
        """Subscribe to SHC events and cache device_id."""
        await super().async_added_to_hass()
        self._cached_device_id = await async_get_device_id(
            self._hass, self._device.id
        )
        # Subscribe AFTER device_id is cached so events never fire with
        # device_id=None during the startup window (#288-cluster).
        if self._service is not None:
            self._service.subscribe_callback(
                self._device.id + "_eventlistener", self._input_events_handler
            )

    def _input_events_handler(self):
        """Handle device input events (called from SHCPollingThread)."""
        self._hass.loop.call_soon_threadsafe(
            self._hass.bus.fire,
            EVENT_BOSCH_SHC,
            {
                ATTR_DEVICE_ID: self._cached_device_id,
                ATTR_ID: self._device.id,
                ATTR_NAME: self._device.name,
                ATTR_EVENT_TYPE: "ALARM",
                ATTR_EVENT_SUBTYPE: self._device.alarm.name,
            },
        )

    @callback
    def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        LOGGER.debug("Stopping alarm event listener for %s", self._device.name)
        self._service.unsubscribe_callback(self._device.id + "_eventlistener")

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.alarm
            != SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_OFF
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:smoke-detector"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "alarm_state": self._device.alarm.name,
        }


class TwinguardAlarmTracker:
    """Track which Twinguard device(s) are actively triggering a smoke alarm.

    The SHC does not expose per-device alarm state directly on the Twinguard.
    Instead the shared SMOKE_DETECTION_SYSTEM fires a SurveillanceAlarm callback
    and the /messages endpoint carries SMOKE_ALARM messages whose
    ``arguments.surveillanceEvents[].triggerId`` maps back to the individual
    Twinguard device id.

    Thread-safety: subscribe_callback fires from SHCPollingThread.
    ``refresh()`` does blocking HTTP and MUST NOT be called from the event loop.
    Listeners are always called via ``hass.loop.call_soon_threadsafe``.
    """

    def __init__(
        self,
        session: SHCSession,
        smoke_detection_system: SHCSmokeDetectionSystem,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the tracker (no I/O; call refresh() separately)."""
        self._session = session
        self._smoke_detection_system = smoke_detection_system
        self._hass = hass
        self._service = None
        self._listeners: list[tuple[HomeAssistant, Callable[[], None]]] = []
        self._active_trigger_ids: set[str] = set()
        self._last_alarm_state: str | None = None
        self._torn_down = False

        for service in self._smoke_detection_system.device_services:
            if service.id == "SurveillanceAlarm":
                self._service = service
                self._service.subscribe_callback(
                    self._smoke_detection_system.id + "_twinguard_alarm_listener",
                    self._handle_alarm_update,
                )
                break

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def alarm_state(self) -> str | None:
        """Return the global surveillance alarm state name."""
        try:
            return self._smoke_detection_system.alarm.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown smoke detection system alarm state for %s: %s",
                self._smoke_detection_system.name,
                err,
            )
            return None

    def register_listener(self, hass: HomeAssistant, listener: Callable[[], None]) -> None:
        """Register a listener (called from event loop via async_added_to_hass)."""
        self._listeners.append((hass, listener))

    def unregister_listener(self, listener: Callable[[], None]) -> None:
        """Unregister a listener by the listener callable."""
        self._listeners = [(h, cb) for (h, cb) in self._listeners if cb is not listener]

    def is_alarm_active_for(self, device_id: str) -> bool:
        """Return whether a smoke alarm is active for the given Twinguard device id."""
        return device_id in self._active_trigger_ids

    async def async_refresh(self) -> None:
        """Refresh active trigger ids from the SHC (async; on the event loop).

        Safe to call multiple times; skips notification if state did not change.
        """
        if self._torn_down:
            return
        alarm_state = self.alarm_state
        if (
            alarm_state
            == SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_OFF.name
        ):
            new_trigger_ids: set[str] = set()
        else:
            new_trigger_ids = await self._extract_trigger_ids_from_messages()

        if (
            new_trigger_ids == self._active_trigger_ids
            and alarm_state == self._last_alarm_state
        ):
            return

        self._active_trigger_ids = new_trigger_ids
        self._last_alarm_state = alarm_state
        self._notify_listeners()

    def teardown(self) -> None:
        """Unsubscribe from the SHC service and clear all listeners.

        Called on config-entry unload and on EVENT_HOMEASSISTANT_STOP.
        Idempotent — safe to call more than once.
        """
        if self._torn_down:
            return
        self._torn_down = True
        self._listeners = []
        if self._service is not None:
            self._service.unsubscribe_callback(
                self._smoke_detection_system.id + "_twinguard_alarm_listener"
            )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _handle_alarm_update(self) -> None:
        """Handle a SurveillanceAlarm update (fired on the event loop).

        The async session fires this callback on the loop; schedule the async
        refresh (it awaits get_messages) as a task so the poll loop isn't
        blocked on the follow-up HTTP call.
        """
        self._hass.async_create_task(self.async_refresh())

    async def _extract_trigger_ids_from_messages(self) -> set[str]:
        """Extract active Twinguard trigger ids from SMOKE_ALARM messages."""
        try:
            messages = await self._session.api.get_messages()

            trigger_ids: set[str] = set()
            for message in messages:
                # Defensive: messageCode may not be a dict (malformed payload).
                message_code = message.get("messageCode", {})
                if not isinstance(message_code, dict):
                    continue
                if message_code.get("name") != "SMOKE_ALARM":
                    continue
                if message.get("sourceId") != self._smoke_detection_system.id:
                    continue

                # Defensive: arguments may not be a dict (malformed payload).
                # triggerId==device.id is assumed based on observed message shape;
                # pending rawscan confirmation (#203).
                arguments = message.get("arguments", {})
                if not isinstance(arguments, dict):
                    continue

                events = self._parse_surveillance_events(
                    arguments.get("surveillanceEvents")
                )
                # A message that contains an ALARM_OFF event signals the end of that
                # alarm cycle — skip the whole message so we don't re-add its triggers.
                if any(event.get("type") == "ALARM_OFF" for event in events):
                    continue

                for event in events:
                    trigger_id = event.get("triggerId")
                    if trigger_id:
                        trigger_ids.add(trigger_id)

        except Exception as err:  # pylint: disable=broad-except
            LOGGER.warning("Unable to fetch Bosch SHC messages: %s", err)
            return self._active_trigger_ids

        return trigger_ids

    @staticmethod
    def _parse_surveillance_events(raw_events) -> list[dict]:
        """Parse surveillanceEvents from a Bosch SHC message payload.

        The field may already be a list (native JSON parse) or a JSON-encoded
        string (observed in some firmware versions).
        """
        if isinstance(raw_events, list):
            return [e for e in raw_events if isinstance(e, dict)]
        if not raw_events:
            return []
        try:
            parsed = json.loads(raw_events)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [e for e in parsed if isinstance(e, dict)]

    def _notify_listeners(self) -> None:
        """Notify all registered entity listeners (threadsafe via event loop)."""
        for hass, listener in list(self._listeners):
            hass.loop.call_soon_threadsafe(listener)


class TwinguardSmokeAlarmSensor(SHCEntity, BinarySensorEntity):
    """Per-Twinguard binary sensor: True when that device is the active smoke alarm source."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE

    def __init__(
        self,
        device: SHCDevice,
        entry_id: str,
        tracker: TwinguardAlarmTracker,
    ) -> None:
        """Initialize the Twinguard smoke alarm sensor."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_name = "Smoke"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_smoke"
        self._tracker = tracker
        self._tracker_listener = self._handle_tracker_update

    async def async_added_to_hass(self) -> None:
        """Register with tracker when entity is added to HA."""
        await super().async_added_to_hass()
        self._tracker.register_listener(self.hass, self._tracker_listener)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from tracker when entity is removed."""
        self._tracker.unregister_listener(self._tracker_listener)
        await super().async_will_remove_from_hass()

    @callback
    def _handle_tracker_update(self) -> None:
        """Called on the event loop when tracker state changes."""
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True when this Twinguard is the source of an active smoke alarm."""
        return self._tracker.is_alarm_active_for(self._device.id)

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:smoke-detector"

    async def async_request_smoketest(self) -> None:
        """Request a Twinguard smoke test."""
        LOGGER.debug("Requesting smoke test on entity %s", self.name)
        await self._device.async_smoketest_requested()

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "alarm_state": self._tracker.alarm_state,
        }


class BatterySensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC battery reporting sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC temperature reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Battery"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_battery"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        """Return the state of the sensor.

        Returns True (battery problem) only for LOW_BATTERY, CRITICAL_LOW, and
        CRITICALLY_LOW_BATTERY.  NOT_AVAILABLE means the device has not yet
        reported battery state — this must NOT be treated as a low-battery
        condition.
        """
        level = self._device.batterylevel
        BatteryState = SHCBatteryDevice.BatteryLevelService.State

        if level == BatteryState.NOT_AVAILABLE:
            LOGGER.debug("Battery state of device %s is not available", self.name)
            return False

        if level == BatteryState.CRITICAL_LOW:
            LOGGER.warning("Battery state of device %s is critical low", self.name)

        if level == BatteryState.CRITICALLY_LOW_BATTERY:
            LOGGER.warning(
                "Battery state of device %s is critically low", self.name
            )

        if level == BatteryState.LOW_BATTERY:
            LOGGER.warning("Battery state of device %s is low", self.name)

        return level != BatteryState.OK


class OccupancyDetectionSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC Motion Detector II [+M] occupancy sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, device: SHCMotionDetector2, entry_id: str) -> None:
        """Initialize the occupancy detection sensor."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_name = "Occupancy"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_occupancy"

    @property
    def is_on(self) -> bool:
        """Return True when the zone is occupied."""
        return self._device.occupied

    @property
    def extra_state_attributes(self):
        """Return last occupancy change time as an extra attribute."""
        return {
            "last_occupancy_change": self._device.last_occupancy_change_time,
        }


class TamperSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC Motion Detector II [+M] tamper sensor.

    Reports True when the device housing was opened/tampered with.
    Reads was_tampered from the LatestTamperService via the model accessor.
    """

    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device, entry_id: str) -> None:
        """Initialize the tamper sensor."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_name = "Tamper"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_tamper"

    @property
    def is_on(self) -> bool:
        """Return True when the device has been tampered with."""
        return bool(getattr(self._device, "was_tampered", False))

    @property
    def extra_state_attributes(self):
        """Return the last tamper time as an extra attribute."""
        return {
            "last_tamper_time": getattr(self._device, "last_tamper_time", None),
        }
