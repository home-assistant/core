"""Homematic base entity."""
from abc import abstractmethod
from datetime import timedelta
import logging

from homeassistant.const import ATTR_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_ADDRESS,
    ATTR_CHANNEL,
    ATTR_INTERFACE,
    ATTR_PARAM,
    ATTR_UNIQUE_ID,
    DATA_HOMEMATIC,
    DOMAIN,
    HM_ATTRIBUTE_SUPPORT,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_HUB = timedelta(seconds=300)
SCAN_INTERVAL_VARIABLES = timedelta(seconds=30)


class HMDevice(Entity):
    """The HomeMatic device base object."""

    def __init__(self, config):
        """Initialize a generic HomeMatic device."""
        self._name = config.get(ATTR_NAME)
        self._address = config.get(ATTR_ADDRESS)
        self._interface = config.get(ATTR_INTERFACE)
        self._channel = config.get(ATTR_CHANNEL)
        self._state = config.get(ATTR_PARAM)
        self._unique_id = config.get(ATTR_UNIQUE_ID)
        self._data = {}
        self._homematic = None
        self._hmdevice = None
        self._connected = False
        self._available = False
        self._channel_map = set()

        # Set parameter to uppercase
        if self._state:
            self._state = self._state.upper()

    async def async_added_to_hass(self):
        """Load data init callbacks."""
        await self.hass.async_add_job(self._subscribe_homematic_events)

    @property
    def unique_id(self):
        """Return unique ID. HomeMatic entity IDs are unique by default."""
        return self._unique_id.replace(" ", "_")

    @property
    def should_poll(self):
        """Return false. HomeMatic states are pushed by the XML-RPC Server."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        # Generate a dictionary with attributes
        for node, data in HM_ATTRIBUTE_SUPPORT.items():
            # Is an attribute and exists for this object
            if node in self._data:
                value = data[1].get(self._data[node], self._data[node])
                attr[data[0]] = value

        # Static attributes
        attr["id"] = self._hmdevice.ADDRESS
        attr["interface"] = self._interface

        return attr

    def update(self):
        """Connect to HomeMatic init values."""
        if self._connected:
            return True

        # Initialize
        self._homematic = self.hass.data[DATA_HOMEMATIC]
        self._hmdevice = self._homematic.devices[self._interface][self._address]
        self._connected = True

        try:
            # Initialize datapoints of this object
            self._init_data()
            self._load_data_from_hm()

            # Link events from pyhomematic
            self._available = not self._hmdevice.UNREACH
        except Exception as err:  # pylint: disable=broad-except
            self._connected = False
            _LOGGER.error("Exception while linking %s: %s", self._address, str(err))

    def _hm_event_callback(self, device, caller, attribute, value):
        """Handle all pyhomematic device events."""
        has_changed = False

        # Is data needed for this instance?
        if f"{attribute}:{device.partition(':')[2]}" in self._channel_map:
            self._data[attribute] = value
            has_changed = True

        # Availability has changed
        if self.available != (not self._hmdevice.UNREACH):
            self._available = not self._hmdevice.UNREACH
            has_changed = True

        # If it has changed data point, update Home Assistant
        if has_changed:
            self.schedule_update_ha_state()

    def _subscribe_homematic_events(self):
        """Subscribe all required events to handle job."""
        for metadata in (
            self._hmdevice.SENSORNODE,
            self._hmdevice.BINARYNODE,
            self._hmdevice.ATTRIBUTENODE,
            self._hmdevice.WRITENODE,
            self._hmdevice.EVENTNODE,
            self._hmdevice.ACTIONNODE,
        ):
            for node, channels in metadata.items():
                # Data is needed for this instance
                if node in self._data:
                    # chan is current channel
                    if len(channels) == 1:
                        channel = channels[0]
                    else:
                        channel = self._channel
                    # Remember the channel for this attribute to ignore invalid events later
                    self._channel_map.add(f"{node}:{channel!s}")

        # Set callbacks
        self._hmdevice.setEventCallback(callback=self._hm_event_callback, bequeath=True)

    def _load_data_from_hm(self):
        """Load first value from pyhomematic."""
        if not self._connected:
            return False

        # Read data from pyhomematic
        for metadata, funct in (
            (self._hmdevice.ATTRIBUTENODE, self._hmdevice.getAttributeData),
            (self._hmdevice.WRITENODE, self._hmdevice.getWriteData),
            (self._hmdevice.SENSORNODE, self._hmdevice.getSensorData),
            (self._hmdevice.BINARYNODE, self._hmdevice.getBinaryData),
        ):
            for node in metadata:
                if metadata[node] and node in self._data:
                    self._data[node] = funct(name=node, channel=self._channel)

        return True

    def _hm_set_state(self, value):
        """Set data to main datapoint."""
        if self._state in self._data:
            self._data[self._state] = value

    def _hm_get_state(self):
        """Get data from main datapoint."""
        if self._state in self._data:
            return self._data[self._state]
        return None

    def _init_data(self):
        """Generate a data dict (self._data) from the HomeMatic metadata."""
        # Add all attributes to data dictionary
        for data_note in self._hmdevice.ATTRIBUTENODE:
            self._data.update({data_note: None})

        # Initialize device specific data
        self._init_data_struct()

    @abstractmethod
    def _init_data_struct(self):
        """Generate a data dictionary from the HomeMatic device metadata."""


class HMHub(Entity):
    """The HomeMatic hub. (CCU2/HomeGear)."""

    def __init__(self, hass, homematic, name):
        """Initialize HomeMatic hub."""
        self.hass = hass
        self.entity_id = f"{DOMAIN}.{name.lower()}"
        self._homematic = homematic
        self._variables = {}
        self._name = name
        self._state = None

        # Load data
        self.hass.helpers.event.track_time_interval(self._update_hub, SCAN_INTERVAL_HUB)
        self.hass.add_job(self._update_hub, None)

        self.hass.helpers.event.track_time_interval(
            self._update_variables, SCAN_INTERVAL_VARIABLES
        )
        self.hass.add_job(self._update_variables, None)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return false. HomeMatic Hub object updates variables."""
        return False

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attr = self._variables.copy()
        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:gradient"

    def _update_hub(self, now):
        """Retrieve latest state."""
        service_message = self._homematic.getServiceMessages(self._name)
        state = None if service_message is None else len(service_message)

        # state have change?
        if self._state != state:
            self._state = state
            self.schedule_update_ha_state()

    def _update_variables(self, now):
        """Retrieve all variable data and update hmvariable states."""
        variables = self._homematic.getAllSystemVariables(self._name)
        if variables is None:
            return

        state_change = False
        for key, value in variables.items():
            if key in self._variables and value == self._variables[key]:
                continue

            state_change = True
            self._variables.update({key: value})

        if state_change:
            self.schedule_update_ha_state()

    def hm_set_variable(self, name, value):
        """Set variable value on CCU/Homegear."""
        if name not in self._variables:
            _LOGGER.error("Variable %s not found on %s", name, self.name)
            return
        old_value = self._variables.get(name)
        if isinstance(old_value, bool):
            value = cv.boolean(value)
        else:
            value = float(value)
        self._homematic.setSystemVariable(self.name, name, value)

        self._variables.update({name: value})
        self.schedule_update_ha_state()
