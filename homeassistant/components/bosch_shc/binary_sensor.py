"""Platform for binarysensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import json
import logging
from typing import TYPE_CHECKING, Any, override

from boschshcpy import (
    BatteryLevelService,
    SHCBatteryDevice,
    SHCShutterContact,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    ) is not None:
        entities.extend(
            TwinguardSmokeSensor(
                hass=hass,
                device=twinguard,
                parent_id=shc_info.unique_id,
                entry_id=config_entry.entry_id,
                smoke_detection_system=smoke_detection_system,
                session=session,
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


def _parse_surveillance_events(raw_events: Any) -> list[dict[str, Any]]:
    """Return the surveillance events of a message as a list of dicts.

    Some firmware versions send the field as a JSON-encoded string.
    """
    if isinstance(raw_events, str):
        try:
            raw_events = json.loads(raw_events)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw_events, list):
        return []
    return [event for event in raw_events if isinstance(event, dict)]


class TwinguardSmokeSensor(SHCEntity, BinarySensorEntity):
    """Smoke alarm of a single Twinguard.

    The controller reports the alarm on the shared smoke detection system.
    The Twinguard that triggered it is named in the SMOKE_ALARM message.
    """

    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _device: SHCTwinguard

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        smoke_detection_system: Any,
        session: Any,
    ) -> None:
        """Initialize a Twinguard smoke sensor."""
        super().__init__(hass, device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_smoke"
        self._smoke_detection_system = smoke_detection_system
        self._session = session
        self._alarm_active = False
        self._refresh_generation = 0
        self._applied_generation = 0
        self._removed = False

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the smoke detection system."""
        await super().async_added_to_hass()
        callback_id = f"{self._attr_unique_id}_alarm"

        def on_alarm_changed() -> None:
            self.hass.add_job(self._async_refresh)

        for service in self._smoke_detection_system.device_services:
            if service.id == "SurveillanceAlarm":
                service.subscribe_callback(callback_id, on_alarm_changed)
                self.async_on_remove(partial(service.unsubscribe_callback, callback_id))
        await self._async_refresh()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop applying results of in-flight refreshes."""
        self._removed = True
        await super().async_will_remove_from_hass()

    @property
    @override
    def is_on(self) -> bool:
        """Return true if this Twinguard raised the active smoke alarm."""
        return self._alarm_active

    async def _async_refresh(self) -> None:
        """Update the alarm state from the controller messages."""
        self._refresh_generation += 1
        generation = self._refresh_generation
        if (
            self._smoke_detection_system.alarm
            == SurveillanceAlarmService.State.ALARM_OFF
        ):
            active = False
        else:
            try:
                messages = await self.hass.async_add_executor_job(
                    self._session.api.get_messages
                )
            except Exception:
                _LOGGER.warning("Unable to fetch Bosch SHC messages", exc_info=True)
                return
            active = self._is_triggered_by_device(messages)
        if self._removed or generation < self._applied_generation:
            return
        self._applied_generation = generation
        if active != self._alarm_active:
            self._alarm_active = active
            self.async_write_ha_state()

    def _is_triggered_by_device(self, messages: Any) -> bool:
        """Return true if an open SMOKE_ALARM message names this Twinguard."""
        for message in messages:
            code = message.get("messageCode")
            if not isinstance(code, dict) or code.get("name") != "SMOKE_ALARM":
                continue
            if message.get("sourceId") != self._smoke_detection_system.id:
                continue
            arguments = message.get("arguments")
            if not isinstance(arguments, dict):
                continue
            events = _parse_surveillance_events(arguments.get("surveillanceEvents"))
            if any(event.get("type") == "ALARM_OFF" for event in events):
                continue
            # The Bosch app reads this field as "device", the SHC writes "triggerId".
            if any(
                self._device.id in (event.get("triggerId"), event.get("device"))
                for event in events
            ):
                return True
        return False
