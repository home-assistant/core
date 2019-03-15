"""Support for HomematicIP Cloud binary sensor."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice)
from homeassistant.components.homematicip_cloud.device import (
    ATTR_GROUP_MEMBER_UNREACHABLE)

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_MOTIONDETECTED = 'motion detected'
ATTR_PRESENCEDETECTED = 'presence detected'
ATTR_POWERMAINSFAILURE = 'power mains failure'
ATTR_WINDOWSTATE = 'window state'
ATTR_MOISTUREDETECTED = 'moisture detected'
ATTR_WATERLEVELDETECTED = 'water level detected'
ATTR_SMOKEDETECTORALARM = 'smoke detector alarm'


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

    from homematicip.aio.group import (
        AsyncSecurityGroup, AsyncSecurityZoneGroup)

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
        if isinstance(group, AsyncSecurityGroup):
            devices.append(HomematicipSecuritySensorGroup(home, group))
        elif isinstance(group, AsyncSecurityZoneGroup):
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
    """Representation of a HomematicIP Cloud security zone group."""

    def __init__(self, home, device, post='SecurityZone'):
        """Initialize security zone group."""
        device.modelType = 'HmIP-{}'.format(post)
        super().__init__(home, device, post)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'safety'

    @property
    def available(self):
        """Security-Group available."""
        # A security-group must be available, and should not be affected by
        # the individual availability of group members.
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the security zone group."""
        attr = super().device_state_attributes

        if self._device.motionDetected:
            attr[ATTR_MOTIONDETECTED] = True
        if self._device.presenceDetected:
            attr[ATTR_PRESENCEDETECTED] = True
        from homematicip.base.enums import WindowState
        if self._device.windowState is not None and \
                self._device.windowState != WindowState.CLOSED:
            attr[ATTR_WINDOWSTATE] = str(self._device.windowState)
        if self._device.unreach:
            attr[ATTR_GROUP_MEMBER_UNREACHABLE] = True
        return attr

    @property
    def is_on(self):
        """Return true if security issue detected."""
        if self._device.motionDetected or \
                self._device.presenceDetected or \
                self._device.unreach or \
                self._device.sabotage:
            return True
        from homematicip.base.enums import WindowState
        if self._device.windowState is not None and \
                self._device.windowState != WindowState.CLOSED:
            return True
        return False


class HomematicipSecuritySensorGroup(HomematicipSecurityZoneSensorGroup,
                                     BinarySensorDevice):
    """Representation of a HomematicIP security group."""

    def __init__(self, home, device):
        """Initialize security group."""
        super().__init__(home, device, 'Sensors')

    @property
    def device_state_attributes(self):
        """Return the state attributes of the security group."""
        attr = super().device_state_attributes

        if self._device.powerMainsFailure:
            attr[ATTR_POWERMAINSFAILURE] = True
        if self._device.moistureDetected:
            attr[ATTR_MOISTUREDETECTED] = True
        if self._device.waterlevelDetected:
            attr[ATTR_WATERLEVELDETECTED] = True
        from homematicip.base.enums import SmokeDetectorAlarmType
        if self._device.smokeDetectorAlarmType is not None and \
                self._device.smokeDetectorAlarmType != \
                SmokeDetectorAlarmType.IDLE_OFF:
            attr[ATTR_SMOKEDETECTORALARM] = \
                str(self._device.smokeDetectorAlarmType)

        return attr

    @property
    def is_on(self):
        """Return true if safety issue detected."""
        parent_is_on = super().is_on
        from homematicip.base.enums import SmokeDetectorAlarmType
        if parent_is_on or \
                self._device.powerMainsFailure or \
                self._device.moistureDetected or \
                self._device.waterlevelDetected or \
                self._device.lowBat:
            return True
        if self._device.smokeDetectorAlarmType is not None and \
                self._device.smokeDetectorAlarmType != \
                SmokeDetectorAlarmType.IDLE_OFF:
            return True
        return False
