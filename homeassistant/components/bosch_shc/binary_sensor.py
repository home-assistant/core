"""Platform for binarysensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, override

from boschshcpy import (
    BatteryLevelService,
    SHCBatteryDevice,
    SHCShutterContact,
    SHCSmokeDetectionSystem,
    SHCTwinguard,
    ShutterContactService,
    SurveillanceAlarmService,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SHCShutterContactSensorEntityDescription(BinarySensorEntityDescription):
    """Describes a SHC shutter contact binary sensor."""

    is_on_fn: Callable[[SHCShutterContact], bool]


SHUTTER_CONTACT_DESCRIPTION = SHCShutterContactSensorEntityDescription(
    key="shutter_contact",
    is_on_fn=lambda device: device.state is ShutterContactService.State.OPEN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC binary sensor platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[BinarySensorEntity] = [
        ShutterContactSensor(
            hass=hass,
            device=binary_sensor,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            entity_description=SHUTTER_CONTACT_DESCRIPTION,
        )
        for binary_sensor in (
            *session.device_helper.shutter_contacts,
            *session.device_helper.shutter_contacts2,
        )
    ]

    entities.extend(
        BatterySensor(
            hass=hass,
            device=binary_sensor,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for binary_sensor in (
            *session.device_helper.motion_detectors,
            *session.device_helper.shutter_contacts,
            *session.device_helper.shutter_contacts2,
            *session.device_helper.smoke_detectors,
            *session.device_helper.thermostats,
            *session.device_helper.twinguards,
            *session.device_helper.universal_switches,
            *session.device_helper.wallthermostats,
            *session.device_helper.water_leakage_detectors,
        )
    )

    if (
        smoke_detection_system := session.device_helper.smoke_detection_system
    ) is not None and session.device_helper.twinguards:
        tracker = TwinguardAlarmTracker(hass, smoke_detection_system)
        config_entry.async_on_unload(tracker.async_stop)
        entities.extend(
            TwinguardSmokeSensor(
                hass=hass,
                device=twinguard,
                parent_id=shc_info.unique_id,
                entry_id=config_entry.entry_id,
                tracker=tracker,
            )
            for twinguard in session.device_helper.twinguards
        )

    async_add_entities(entities)


class ShutterContactSensor(SHCEntity, BinarySensorEntity):
    """Representation of an SHC shutter contact sensor."""

    _attr_name = None
    _device: SHCShutterContact
    entity_description: SHCShutterContactSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        entity_description: SHCShutterContactSensorEntityDescription,
    ) -> None:
        """Initialize an SHC shutter contact sensor."""
        self.entity_description = entity_description
        super().__init__(hass, device, parent_id, entry_id)
        switcher: dict[str | None, BinarySensorDeviceClass] = {
            "ENTRANCE_DOOR": BinarySensorDeviceClass.DOOR,
            "REGULAR_WINDOW": BinarySensorDeviceClass.WINDOW,
            "FRENCH_WINDOW": BinarySensorDeviceClass.DOOR,
            "GENERIC": BinarySensorDeviceClass.WINDOW,
        }
        self._attr_device_class = switcher.get(
            self._device.device_class, BinarySensorDeviceClass.WINDOW
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self._device)


class BatterySensor(SHCEntity, BinarySensorEntity):
    """Representation of an SHC battery reporting sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _device: SHCBatteryDevice

    def __init__(
        self, hass: HomeAssistant, device: SHCDevice, parent_id: str, entry_id: str
    ) -> None:
        """Initialize an SHC battery reporting sensor."""
        super().__init__(hass, device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_battery"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.batterylevel is not BatteryLevelService.State.OK


RETRY_DELAY = 30


class TwinguardAlarmTracker:
    """Track which Twinguards triggered the active smoke alarm.

    The controller reports a smoke alarm on the shared smoke detection system.
    The Twinguards that raised it are named in its SMOKE_ALARM message. The
    messages are requested once per alarm update and shared by all sensors.
    """

    def __init__(
        self, hass: HomeAssistant, smoke_detection_system: SHCSmokeDetectionSystem
    ) -> None:
        """Initialize the tracker and subscribe to the alarm state."""
        self._hass = hass
        self._system = smoke_detection_system
        self._callback_id = f"{smoke_detection_system.id}_twinguard_alarm"
        self._listeners: list[CALLBACK_TYPE] = []
        self._retry: CALLBACK_TYPE | None = None
        self._stopped = False
        self._generation = 0
        self.trigger_ids: set[str] = set()
        self.available = (
            smoke_detection_system.alarm is SurveillanceAlarmService.State.ALARM_OFF
        )
        self._services = [
            service
            for service in smoke_detection_system.device_services
            if service.id == "SurveillanceAlarm"
        ]
        for service in self._services:
            service.subscribe_callback(self._callback_id, self._on_alarm_changed)

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Add a listener that is called when the tracked state changes."""
        self._listeners.append(listener)
        if len(self._listeners) == 1:
            self._hass.async_create_task(self.async_refresh())
        return partial(self._listeners.remove, listener)

    @callback
    def async_stop(self) -> None:
        """Unsubscribe and stop all pending work."""
        self._stopped = True
        self._cancel_retry()
        for service in self._services:
            service.unsubscribe_callback(self._callback_id)

    def _on_alarm_changed(self) -> None:
        """Handle an alarm update, called from the SHC polling thread."""
        self._hass.add_job(self.async_refresh)

    def _cancel_retry(self) -> None:
        if self._retry is not None:
            self._retry()
            self._retry = None

    async def async_refresh(self, *_: Any) -> None:
        """Update the trigger ids from the controller messages."""
        self._cancel_retry()
        self._generation += 1
        generation = self._generation
        trigger_ids: set[str] = set()
        available = True
        if self._system.alarm is not SurveillanceAlarmService.State.ALARM_OFF:
            try:
                trigger_ids = await self._hass.async_add_executor_job(
                    self._system.triggered_device_ids
                )
            except Exception:
                _LOGGER.warning("Unable to fetch Bosch SHC messages", exc_info=True)
                available = False
        if self._stopped or generation != self._generation:
            return
        self._cancel_retry()
        if not available:
            self._retry = async_call_later(self._hass, RETRY_DELAY, self.async_refresh)
        if (trigger_ids, available) != (self.trigger_ids, self.available):
            self.trigger_ids = trigger_ids
            self.available = available
            for listener in list(self._listeners):
                listener()


class TwinguardSmokeSensor(SHCEntity, BinarySensorEntity):
    """Smoke alarm of a single Twinguard."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _device: SHCTwinguard

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        tracker: TwinguardAlarmTracker,
    ) -> None:
        """Initialize a Twinguard smoke sensor."""
        super().__init__(hass, device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_smoke"
        self._tracker = tracker

    @override
    async def async_added_to_hass(self) -> None:
        """Listen to the shared alarm tracker."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._tracker.async_add_listener(self.async_write_ha_state)
        )

    @property
    @override
    def available(self) -> bool:
        """Return false if the device or the alarm lookup is unavailable."""
        return super().available and self._tracker.available

    @property
    @override
    def is_on(self) -> bool:
        """Return true if this Twinguard raised the active smoke alarm."""
        return self._device.id in self._tracker.trigger_ids
