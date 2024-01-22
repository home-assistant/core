"""The torque integration."""
from __future__ import annotations
import hashlib
import logging
import re
from .sensor import TorqueSensor

from homeassistant.util import slugify

# from homeassistant.components.device_tracker.const import LOGGER

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform, DEGREE
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_ID
# TODO Replace with following comment after initial PR
from .const import DOMAIN, SENSOR_TIME_FIELD, SENSORS, API_PATH, SENSOR_ID_FIELD, SENSOR_NAME_KEY, SENSOR_UNIT_KEY, SENSOR_VALUE_KEY
# from .const import DOMAIN, SENSOR_TIME_FIELD, SENSORS, API_PATH, SENSOR_ID_FIELD, SENSOR_NAME_KEY, SENSOR_UNIT_KEY, SENSOR_VALUE_KEY, TRACKERS
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store


# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
# NOTE Device Tracker lines have been commented out for initial PR
# PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.DEVICE_TRACKER]
# Delete this line and next once PR has been accepted
PLATFORMS: list[Platform] = [Platform.SENSOR]


NAME_KEY = re.compile(SENSOR_NAME_KEY)
UNIT_KEY = re.compile(SENSOR_UNIT_KEY)
VALUE_KEY = re.compile(SENSOR_VALUE_KEY)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up torque2 from a config entry."""
    # TODO Store an API object for your platforms to access

    coordinator = TorqueDataCoordinator(hass, entry)
    await coordinator.load_stores()

    await coordinator.async_config_entry_first_refresh()

    hass.http.register_view(coordinator)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def convert_pid(value):
    """Convert pid from hex string to integer."""
    return str(int(value, 16))


class TorqueDataCoordinator(DataUpdateCoordinator, HomeAssistantView):
    """Handle data from Torque requests."""

    url = API_PATH
    name = "api:torque"

    def __init__(self, hass, entry: ConfigEntry):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Torque Data Coordinator"
        )

        self._hass = hass
        self._entry: ConfigEntry = entry
        
        # Create the stores
        self.store_custom_units = Store(hass, 1, "torque_sensor_units")
        self.store_available_sensors = Store(hass, 1, "torque_used_sensors")
        
        # Register setup info
        self.raw_id = entry.data.get(CONF_ID)
        self.id = str(hashlib.md5(str(self.raw_id).encode()).hexdigest())
        self.vehicle_name = entry.data.get(CONF_NAME)

        # create defaults
        self.default_sensor_units = {}
        self.default_pids:list = []
        for pid, [name, unit, icon] in SENSORS.items():
            self.default_sensor_units[pid] = unit
            self.default_pids.append(pid)
        # TODO Uncomment the next three lines once Initial PR is complete
        # for pid, [name, unit, icon] in TRACKERS.items():
        #     self.default_sensor_units[pid] = unit
        #     self.default_pids.append(pid)

        self.last_request_time = 0
        self.new_sensors = {}

        # Function to add entities down the line
        self.async_add_entities = None

        # Create vehicle device
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, self.id)},
            manufacturer="Torque",
            name=self.vehicle_name,
            model="OBD II")

    async def load_stores(self):

        self.custom_units = {}
        custom_units = await self.store_custom_units.async_load()
        if custom_units:
            self.custom_units = custom_units
        else:
            await self.store_custom_units.async_save({})

        self.available_sensors = await self.store_available_sensors.async_load()
        if not self.available_sensors:
            await self.store_available_sensors.async_save([])
            self.available_sensors = []

    async def _async_update_data(self):
        return

    @callback
    async def get(self, request):
        """Handle Torque data request."""
        hass: HomeAssistant = request.app["hass"]
        query = request.query

        request_id = query[SENSOR_ID_FIELD]
        request_time = int(query[SENSOR_TIME_FIELD])

        if self.id is not None and self.id != request_id:
            _LOGGER.info(f"Unknown Torque Device ID: {request_id}")  # noqa: G004
            return "OK!"
        
        if request_time < self.last_request_time:
            _LOGGER.debug(f"Stale Request: {request_time}")  # noqa: G004
            return "OK!"
        self.last_request_time = request_time

        values = {}

        query_pids = []

        entity_register: er.EntityRegistry = er.async_get(hass)

        units_changed = False

        for key in query:
            # first query has names, second query has units, third and following have values
            is_name = NAME_KEY.match(key)
            is_unit = UNIT_KEY.match(key)
            is_value = VALUE_KEY.match(key)

            is_thing = is_name or is_unit or is_value 

            # Register used names to the used pid list to make sure they are kept / created
            if is_name:
                pid = convert_pid(is_name.group(1))

            # Register used units to the used pid list to make sure they are kept / created
            elif is_unit:
                pid = convert_pid(is_unit.group(1))
                if pid in self.default_pids:
                    query_pids.append(pid)
                temp_unit = query[key]
                if "\\xC2\\xB0" in temp_unit:
                    temp_unit = temp_unit.replace("\\xC2\\xB0", DEGREE)
                if pid in self.default_sensor_units and temp_unit != self.default_sensor_units[pid]:
                    self.custom_units[pid] = temp_unit
                    units_changed = True

            # Save the values to send to the sensors
            elif is_value:
                pid = convert_pid(is_value.group(1))
                values[pid] = float(query[key])

            # Reprt new pids
            if is_thing and pid not in self.default_pids:
                if pid not in self.new_sensors.keys():
                    self.new_sensors[pid] = ["", ""]
                if is_name:
                    self.new_sensors[pid][0] = query[key]
                if is_unit:
                    self.new_sensors[pid][1] = query[key]
                if is_value and self.new_sensors[pid][0] != "":
                    _LOGGER.warning(f"New Sensor: {pid} - {key} - {self.new_sensors[pid][0]} - {self.new_sensors[pid][1]}")
                    self.new_sensors.pop(pid)

        # Save new units if they have changed
        if units_changed:
                    
            await self.store_custom_units.async_save(self.custom_units)

        # Keep the used pids, and delete the unused ones.
        # If a used one hasn't been created, its tme to do so.
        if query_pids: 

            unused_pids = list(set(self.default_pids) - set(query_pids))
            
            # Delete unsused sensors
            for pid in unused_pids:
                if pid in self.available_sensors:
                    entity_id = "sensor." + slugify(f"{SENSORS[pid][0]}")
                    entity_register.async_remove(entity_id)
                    self.available_sensors.remove(pid)
                    _LOGGER.info(f"Removed pid: {pid}")
            
            sensor_list = []
            # Create used pids that dont exist, but dont create the tracker ones
            new_pids = list(set(query_pids) - set(self.available_sensors))
            for pid in new_pids:
                if pid in self.default_pids:
                    sensor_data = SENSORS[pid]
                    sensor =  TorqueSensor(hass, self, self.id, pid, sensor_data[0], sensor_data[1], sensor_data[2])
                    _LOGGER.info(f"Added pid: {pid}")
                    self.available_sensors.append(pid)
                    sensor_list.append(sensor)

            self.async_add_entities(sensor_list, True)

            await self.store_available_sensors.async_save(self.available_sensors)

        self.async_set_updated_data(values)


    
        return "OK!"
        

