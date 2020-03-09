"""Support for the Philips Hue sensors as a platform."""
import asyncio
from datetime import timedelta
import logging

from aiohttp import client_exceptions
from aiohue import AiohueException, Unauthorized
from aiohue.sensors import TYPE_ZLL_PRESENCE
import async_timeout

from homeassistant.core import callback
from homeassistant.helpers import debounce, entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN as HUE_DOMAIN, REQUEST_REFRESH_DELAY
from .helpers import remove_devices

SENSOR_CONFIG_MAP = {}
_LOGGER = logging.getLogger(__name__)


def _device_id(aiohue_sensor):
    # Work out the shared device ID, as described below
    device_id = aiohue_sensor.uniqueid
    if device_id and len(device_id) > 23:
        device_id = device_id[:23]
    return device_id


class SensorManager:
    """Class that handles registering and updating Hue sensor entities.

    Intended to be a singleton.
    """

    SCAN_INTERVAL = timedelta(seconds=5)

    def __init__(self, bridge):
        """Initialize the sensor manager."""
        self.bridge = bridge
        self._component_add_entities = {}
        self.current = {}
        self.coordinator = DataUpdateCoordinator(
            bridge.hass,
            _LOGGER,
            name="sensor",
            update_method=self.async_update_data,
            update_interval=self.SCAN_INTERVAL,
            request_refresh_debouncer=debounce.Debouncer(
                bridge.hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
            ),
        )

    async def async_update_data(self):
        """Update sensor data."""
        try:
            with async_timeout.timeout(4):
                return await self.bridge.async_request_call(
                    self.bridge.api.sensors.update
                )
        except Unauthorized:
            await self.bridge.handle_unauthorized_error()
            raise UpdateFailed
        except (asyncio.TimeoutError, AiohueException, client_exceptions.ClientError):
            raise UpdateFailed

    async def async_register_component(self, binary, async_add_entities):
        """Register async_add_entities methods for components."""
        self._component_add_entities[binary] = async_add_entities

        if len(self._component_add_entities) < 2:
            return

        # We have all components available, start the updating.
        self.coordinator.async_add_listener(self.async_update_items)
        self.bridge.reset_jobs.append(
            lambda: self.coordinator.async_remove_listener(self.async_update_items)
        )
        await self.coordinator.async_refresh()

    @callback
    def async_update_items(self):
        """Update sensors from the bridge."""
        api = self.bridge.api.sensors

        if len(self._component_add_entities) < 2:
            return

        new_sensors = []
        new_binary_sensors = []
        primary_sensor_devices = {}
        current = self.current

        # Physical Hue motion sensors present as three sensors in the API: a
        # presence sensor, a temperature sensor, and a light level sensor. Of
        # these, only the presence sensor is assigned the user-friendly name
        # that the user has given to the device. Each of these sensors is
        # linked by a common device_id, which is the first twenty-three
        # characters of the unique id (then followed by a hyphen and an ID
        # specific to the individual sensor).
        #
        # To set up neat values, and assign the sensor entities to the same
        # device, we first, iterate over all the sensors and find the Hue
        # presence sensors, then iterate over all the remaining sensors -
        # finding the remaining ones that may or may not be related to the
        # presence sensors.
        for item_id in api:
            if api[item_id].type != TYPE_ZLL_PRESENCE:
                continue

            primary_sensor_devices[_device_id(api[item_id])] = api[item_id]

        # Iterate again now we have all the presence sensors, and add the
        # related sensors with nice names where appropriate.
        for item_id in api:
            existing = current.get(api[item_id].uniqueid)
            if existing is not None:
                continue

            primary_sensor = None
            sensor_config = SENSOR_CONFIG_MAP.get(api[item_id].type)
            if sensor_config is None:
                continue

            base_name = api[item_id].name
            primary_sensor = primary_sensor_devices.get(_device_id(api[item_id]))
            if primary_sensor is not None:
                base_name = primary_sensor.name
            name = sensor_config["name_format"].format(base_name)

            current[api[item_id].uniqueid] = sensor_config["class"](
                api[item_id], name, self.bridge, primary_sensor=primary_sensor
            )
            if sensor_config["binary"]:
                new_binary_sensors.append(current[api[item_id].uniqueid])
            else:
                new_sensors.append(current[api[item_id].uniqueid])

        self.bridge.hass.async_create_task(
            remove_devices(
                self.bridge, [value.uniqueid for value in api.values()], current,
            )
        )

        if new_sensors:
            self._component_add_entities[False](new_sensors)
        if new_binary_sensors:
            self._component_add_entities[True](new_binary_sensors)


class GenericHueSensor(entity.Entity):
    """Representation of a Hue sensor."""

    should_poll = False

    def __init__(self, sensor, name, bridge, primary_sensor=None):
        """Initialize the sensor."""
        self.sensor = sensor
        self._name = name
        self._primary_sensor = primary_sensor
        self.bridge = bridge

    async def _async_update_ha_state(self, *args, **kwargs):
        raise NotImplementedError

    @property
    def primary_sensor(self):
        """Return the primary sensor entity of the physical device."""
        return self._primary_sensor or self.sensor

    @property
    def device_id(self):
        """Return the ID of the physical device this sensor is part of."""
        return self.unique_id[:23]

    @property
    def unique_id(self):
        """Return the ID of this Hue sensor."""
        return self.sensor.uniqueid

    @property
    def name(self):
        """Return a friendly name for the sensor."""
        return self._name

    @property
    def available(self):
        """Return if sensor is available."""
        return self.bridge.sensor_manager.coordinator.last_update_success and (
            self.bridge.allow_unreachable or self.sensor.config["reachable"]
        )

    @property
    def swupdatestate(self):
        """Return detail of available software updates for this device."""
        return self.primary_sensor.raw.get("swupdate", {}).get("state")

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.bridge.sensor_manager.coordinator.async_add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.bridge.sensor_manager.coordinator.async_remove_listener(
            self.async_write_ha_state
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.bridge.sensor_manager.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return the device info.

        Links individual entities together in the hass device registry.
        """
        return {
            "identifiers": {(HUE_DOMAIN, self.device_id)},
            "name": self.primary_sensor.name,
            "manufacturer": self.primary_sensor.manufacturername,
            "model": (self.primary_sensor.productname or self.primary_sensor.modelid),
            "sw_version": self.primary_sensor.swversion,
            "via_device": (HUE_DOMAIN, self.bridge.api.config.bridgeid),
        }


class GenericZLLSensor(GenericHueSensor):
    """Representation of a Hue-brand, physical sensor."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {"battery_level": self.sensor.battery}
