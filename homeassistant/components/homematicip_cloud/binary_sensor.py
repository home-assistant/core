"""Support for HomematicIP Cloud binary sensor."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice)

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)


ATTR_SAFETYISSUES = 'safety issues'
ATTR_SECURITYISSUES = 'security issues'

ISSUE_MOTIONDETECTED = 'motion detected'
ISSUE_PRESENCEDETECTED = 'presence detected'
ISSUE_POWERMAINSFAILURE = 'power mains failure'
ISSUE_WINDOWOPEN = 'window open'
ISSUE_MOISTUREDETECTED = 'moisture detected'
ISSUE_WATERLEVELDETECTED = 'water level detected'
ISSUE_SMOKEDETECTORALARM = 'smoke detector alarm'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud binary sensor devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP Cloud binary sensor from a config entry."""
    from homematicip.aio.device import (
        AsyncShutterContact, AsyncMotionDetectorIndoor, AsyncSmokeDetector,
        AsyncWaterSensor, AsyncRotaryHandleSensor,
        AsyncMotionDetectorPushButton)

    from homematicip.group import (
        SecurityGroup, SecurityZoneGroup)

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, (AsyncShutterContact, AsyncRotaryHandleSensor)):
            devices.append(HomematicipShutterContact(home, device))
        elif isinstance(device, (AsyncMotionDetectorIndoor,
                                 AsyncMotionDetectorPushButton)):
            devices.append(HomematicipMotionDetector(home, device))
        elif isinstance(device, AsyncSmokeDetector):
            devices.append(HomematicipSmokeDetector(home, device))
        elif isinstance(device, AsyncWaterSensor):
            devices.append(HomematicipWaterDetector(home, device))

    for group in home.groups:
        if isinstance(group, SecurityGroup):
            devices.append(HomematicipSecuritySensorGroup(home, group))
        elif isinstance(group, SecurityZoneGroup):
            devices.append(HomematicipSecurityZoneSensorGroup(home, group))

    if devices:
        async_add_entities(devices)


class HomematicipShutterContact(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud shutter contact."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'door'

    @property
    def is_on(self):
        """Return true if the shutter contact is on/open."""
        from homematicip.base.enums import WindowState

        if self._device.sabotage:
            return True
        if self._device.windowState is None:
            return None
        return self._device.windowState != WindowState.CLOSED


class HomematicipMotionDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud motion detector."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'motion'

    @property
    def is_on(self):
        """Return true if motion is detected."""
        if self._device.sabotage:
            return True
        return self._device.motionDetected


class HomematicipSmokeDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud smoke detector."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'smoke'

    @property
    def is_on(self):
        """Return true if smoke is detected."""
        from homematicip.base.enums import SmokeDetectorAlarmType
        return (self._device.smokeDetectorAlarmType
                != SmokeDetectorAlarmType.IDLE_OFF)


class HomematicipWaterDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud water detector."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'moisture'

    @property
    def is_on(self):
        """Return true if moisture or waterlevel is detected."""
        return self._device.moistureDetected or self._device.waterlevelDetected


class HomematicipSecurityZoneSensorGroup(HomematicipGenericDevice,
                                         BinarySensorDevice):
    """Representation of a HomematicIP Cloud water detector."""

    def __init__(self, home, device, post='SecurityZone'):
        """Initialize heating group."""
        device.modelType = 'HmIP-{}'.format(post)
        super().__init__(home, device, post)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'safety'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = super().device_state_attributes

        security_issues = []
        if self._device.motionDetected is True:
            security_issues.append(ISSUE_MOTIONDETECTED)
        if self._device.presenceDetected is True:
            security_issues.append(ISSUE_PRESENCEDETECTED)
        from homematicip.base.enums import WindowState
        if self._device.windowState is not None and \
                self._device.windowState != WindowState.CLOSED:
            security_issues.append(ISSUE_WINDOWOPEN)

        if security_issues.__len__() > 0:
            attr.update({ATTR_SECURITYISSUES: ', '.join(security_issues)})

        return attr

    @property
    def is_on(self):
        """Return true if security issue detected."""
        from homematicip.base.enums import WindowState
        if self._device.motionDetected is True or \
                self._device.presenceDetected is True:
            return True
        if self._device.windowState is not None and \
                self._device.windowState != WindowState.CLOSED:
            return True
        return False


class HomematicipSecuritySensorGroup(HomematicipSecurityZoneSensorGroup,
                                     BinarySensorDevice):
    """Representation of a HomematicIP Cloud water detector."""

    def __init__(self, home, device):
        """Initialize heating group."""
        super().__init__(home, device, 'SecuritySensors')

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = super().device_state_attributes

        safety_issues = []
        if self._device.powerMainsFailure is True:
            safety_issues.append(ISSUE_POWERMAINSFAILURE)
        if self._device.moistureDetected is True:
            safety_issues.append(ISSUE_MOISTUREDETECTED)
        if self._device.waterlevelDetected is True:
            safety_issues.append(ISSUE_WATERLEVELDETECTED)
        from homematicip.base.enums import SmokeDetectorAlarmType
        if self._device.smokeDetectorAlarmType is not None and \
                self._device.smokeDetectorAlarmType != \
                SmokeDetectorAlarmType.IDLE_OFF:
            safety_issues.append(ISSUE_SMOKEDETECTORALARM)

        if safety_issues.__len__() > 0:
            attr.update({ATTR_SAFETYISSUES: ', '.join(safety_issues)})

        return attr

    @property
    def is_on(self):
        """Return true if security issue detected."""
        parent_is_on = super().is_on
        from homematicip.base.enums import SmokeDetectorAlarmType
        if parent_is_on is True or \
                self._device.powerMainsFailure is True or \
                self._device.moistureDetected is True or \
                self._device.waterlevelDetected is True:
            return True
        if self._device.smokeDetectorAlarmType is not None and \
                self._device.smokeDetectorAlarmType != \
                SmokeDetectorAlarmType.IDLE_OFF:
            return True
        return False
