"""Add sensors for TP-Link Omada Controller."""
import logging

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as OMADA_DOMAIN, SENSOR_AP_STATS_DICT, SENSOR_DICT

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TP-Link Omada Sensors."""
    # Get Main Sensors
    omada = hass.data[OMADA_DOMAIN][entry.data[CONF_NAME]]
    sensors = [
        OmadaSensor(omada, sensor_name, entry.entry_id) for sensor_name in SENSOR_DICT
    ]
    async_add_entities(sensors, True)
    # Get SSID Sensors
    sensors = [
        OmadaSSIDSensor(omada, ssid_name, entry.entry_id)
        for ssid_name in omada.ssid_attrs
    ]
    async_add_entities(sensors, True)
    # Get AP Sensors
    sensors = [
        OmadaAPSensor(
            omada,
            ap_mac,
            omada.access_points_settings[ap_mac],
            sensor_name,
            entry.entry_id,
        )
        for ap_mac, ap_data in omada.access_points_stats.items()
        for sensor_name, sensor_params in ap_data.items()
    ]
    async_add_entities(sensors, True)


class OmadaBaseSensor(Entity):
    """Base class for all Omada sensor."""

    _icon = None
    _unit_of_measurement = None
    omada = None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Omada Controller."""
        return {}

    @property
    def device_id(self):
        """Return the ID of this Hue light."""
        return self.unique_id

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.omada.available


class OmadaSensor(OmadaBaseSensor):
    """Class defining sensor about Omada controller itself."""

    def __init__(self, omada, sensor_name, server_unique_id):
        """Initialize Omada sensor."""
        self.omada = omada
        self._name = omada.name
        self._condition = sensor_name
        self._server_unique_id = server_unique_id

        variable_info = SENSOR_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]
        self.data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._condition_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._condition_name}"

    @property
    def device_info(self):
        """Return the device information of the sensor."""
        return {
            "identifiers": {(OMADA_DOMAIN, self.omada.name)},
            "name": self._name,
            "manufacturer": "TP-Link",
            "connections": [["host", self.omada.host]],
            "sw_version": self.omada.version,
        }

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self.data[self._condition], 2)
        except TypeError:
            return self.data[self._condition]

    async def async_update(self):
        """Get the latest data from the Omada Controller."""
        await self.omada.async_update()
        self.data = self.omada.data


class OmadaSSIDSensor(OmadaBaseSensor):
    """Class defining a sensor about a SSID."""

    def __init__(self, omada, ssid_name, server_unique_id):
        """Initialize Omada SSID sensor."""
        self.omada = omada
        self._name = omada.name
        self._ssid_name = ssid_name
        self._server_unique_id = server_unique_id

        self._unit_of_measurement = "clients"
        self._icon = "mdi:wifi"
        self.value = None
        self.data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} ssid {self._ssid_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/ssid/{self._ssid_name}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Omada Controller."""
        tmp_data = self.data.copy()
        if "connected_clients" in tmp_data:
            tmp_data.pop("connected_clients")
        return tmp_data

    @property
    def device_info(self):
        """Return the device information of the sensor."""
        return {
            "identifiers": {(OMADA_DOMAIN, self.omada.name)},
            "name": self._name,
            "manufacturer": "TP-Link",
            "connections": [["host", self.omada.host]],
            "sw_version": self.omada.version,
        }

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self.value, 2)
        except TypeError:
            return self.value

    async def async_update(self):
        """Get the latest data from the Omada Controller."""
        await self.omada.async_update()
        self.data = self.omada.ssid_stats.get(self._ssid_name, {})
        self.data.update(self.omada.ssid_attrs[self._ssid_name])
        self.value = self.data.get("connected_clients", 0)


class OmadaAPSensor(OmadaBaseSensor):
    """Class defining a sensor about an Access Point."""

    def __init__(self, omada, ap_mac, ap_ids, sensor_name, server_unique_id):
        """Initialize Omada Access Point sensor."""
        self.omada = omada
        self._name = omada.name
        self._ap_mac = ap_mac
        self._ap_ids = ap_ids
        self._ap_name = ap_ids["Name"]
        self._condition = sensor_name
        self._server_unique_id = server_unique_id

        variable_info = SENSOR_AP_STATS_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]
        self.data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._ap_name} {self._condition_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._ap_mac}/{self._condition_name}"

    @property
    def device_info(self):
        """Return the device information of the sensor."""
        return {
            "identifiers": {(OMADA_DOMAIN, self._ap_mac)},
            "name": self._ap_name,
            "manufacturer": "TP-Link",
            "model": self.omada.access_points_settings[self._ap_mac]["Model"],
            "connections": [["mac", self._ap_mac]],
            "sw_version": self.omada.access_points_settings[self._ap_mac]["Version"],
            "via_device": (OMADA_DOMAIN, self.omada.name),
        }

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self.data, 2)
        except TypeError:
            return self.data

    async def async_update(self):
        """Get the latest data from the Omada Controller."""
        await self.omada.async_update()
        self.data = self.omada.access_points_stats[self._ap_mac][self._condition]
