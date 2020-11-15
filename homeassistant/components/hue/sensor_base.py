"""Support for the Philips Hue sensors as a platform."""
from datetime import timedelta
import logging

from aiohue import AiohueException, Unauthorized
from aiohue.sensors import TYPE_ZLL_PRESENCE
import async_timeout

from homeassistant.core import callback
from homeassistant.helpers import debounce, entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REQUEST_REFRESH_DELAY
from .helpers import remove_devices
from .hue_event import EVENT_CONFIG_MAP
from .sensor_device import GenericHueDevice

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
        self.current_events = {}

        self._enabled_platforms = ("binary_sensor", "sensor")
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
        except Unauthorized as err:
            await self.bridge.handle_unauthorized_error()
            raise UpdateFailed("Unauthorized") from err
        except AiohueException as err:
            raise UpdateFailed(f"Hue error: {err}") from err

    async def async_register_component(self, platform, async_add_entities):
        """Register async_add_entities methods for components."""
        self._component_add_entities[platform] = async_add_entities

        if len(self._component_add_entities) < len(self._enabled_platforms):
            _LOGGER.debug("Aborting start with %s, waiting for the rest", platform)
            return

        # We have all components available, start the updating.
        self.bridge.reset_jobs.append(
            self.coordinator.async_add_listener(self.async_update_items)
        )
        await self.coordinator.async_refresh()

    @callback
    def async_update_items(self):
        """Update sensors from the bridge."""
        api = self.bridge.api.sensors

        if len(self._component_add_entities) < len(self._enabled_platforms):
            return

        to_add = {}
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
            uniqueid = api[item_id].uniqueid
            if current.get(uniqueid, self.current_events.get(uniqueid)) is not None:
                continue

            sensor_type = api[item_id].type

            # Check for event generator devices
            event_config = EVENT_CONFIG_MAP.get(sensor_type)
            if event_config is not None:
                base_name = api[item_id].name
                name = event_config["name_format"].format(base_name)
                new_event = event_config["class"](api[item_id], name, self.bridge)
                self.bridge.hass.async_create_task(
                    new_event.async_update_device_registry()
                )
                self.current_events[uniqueid] = new_event

            sensor_config = SENSOR_CONFIG_MAP.get(sensor_type)
            if sensor_config is None:
                continue

            base_name = api[item_id].name
            primary_sensor = primary_sensor_devices.get(_device_id(api[item_id]))
            if primary_sensor is not None:
                base_name = primary_sensor.name
            name = sensor_config["name_format"].format(base_name)

            current[uniqueid] = sensor_config["class"](
                api[item_id], name, self.bridge, primary_sensor=primary_sensor
            )

            to_add.setdefault(sensor_config["platform"], []).append(current[uniqueid])

        self.bridge.hass.async_create_task(
            remove_devices(
                self.bridge,
                [value.uniqueid for value in api.values()],
                current,
            )
        )

        for platform in to_add:
            self._component_add_entities[platform](to_add[platform])


class GenericHueSensor(GenericHueDevice, entity.Entity):
    """Representation of a Hue sensor."""

    should_poll = False

    async def _async_update_ha_state(self, *args, **kwargs):
        raise NotImplementedError

    @property
    def available(self):
        """Return if sensor is available."""
        return self.bridge.sensor_manager.coordinator.last_update_success and (
            self.bridge.allow_unreachable
            # remotes like Hue Tap (ZGPSwitchSensor) have no _reachability_
            or self.sensor.config.get("reachable", True)
        )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.bridge.sensor_manager.coordinator.async_add_listener(
                self.async_write_ha_state
            )
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.bridge.sensor_manager.coordinator.async_request_refresh()


class GenericZLLSensor(GenericHueSensor):
    """Representation of a Hue-brand, physical sensor."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {"battery_level": self.sensor.battery}
