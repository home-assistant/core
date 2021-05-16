"""Platform for binarysensor integration."""
from datetime import datetime, timedelta

from boschshcpy import (
    SHCSession,
    SHCShutterContact,
    SHCSmokeDetectionSystem,
    SHCSmokeDetector,
    SHCWaterLeakageSensor,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC binary sensor platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for binarysensor in session.device_helper.shutter_contacts:
        entities.append(
            ShutterContactSensor(
                device=binarysensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for binarysensor in session.device_helper.motion_detectors:
        entities.append(
            MotionDetectionSensor(
                device=binarysensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for binarysensor in session.device_helper.smoke_detectors:
        entities.append(
            SmokeDetectorSensor(
                device=binarysensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for binarysensor in session.device_helper.smoke_detection_system:
        entities.append(
            SmokeDetectionSystemSensor(
                device=binarysensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for binarysensor in session.device_helper.water_leakage_detectors:
        entities.append(
            WaterLeakageDetectorSensor(
                device=binarysensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class ShutterContactSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC shutter contact sensor."""

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._device.state == SHCShutterContact.ShutterContactService.State.OPEN

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        switcher = {
            "ENTRANCE_DOOR": DEVICE_CLASS_DOOR,
            "REGULAR_WINDOW": DEVICE_CLASS_WINDOW,
            "FRENCH_WINDOW": DEVICE_CLASS_DOOR,
            "GENERIC": DEVICE_CLASS_WINDOW,
        }
        return switcher.get(self._device.device_class, DEVICE_CLASS_WINDOW)


class MotionDetectionSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC motion detection sensor."""

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_MOTION

    @property
    def is_on(self):
        """Return the state of the sensor."""
        try:
            latestmotion = datetime.strptime(
                self._device.latestmotion, "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except ValueError:
            return False

        elapsed = datetime.utcnow() - latestmotion
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

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._device.alarmstate != SHCSmokeDetector.AlarmService.State.IDLE_OFF

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SMOKE

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:smoke-detector"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "smokedetectorcheck_state": self._device.smokedetectorcheck_state.name,
            "alarmstate": self._device.alarmstate.name,
        }


class WaterLeakageDetectorSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC water leakage detector sensor."""

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.leakage_state
            != SHCWaterLeakageSensor.WaterLeakageSensorService.State.NO_LEAKAGE
        )

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_MOISTURE

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:water-alert"


class SmokeDetectionSystemSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC smoke detection system sensor."""

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.alarm
            != SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_OFF
        )

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SMOKE

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
