"""Switch configuration for VegeHub integration."""

import logging
from typing import Any

import aiohttp

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, MODEL
from .errors import CommunicationFailed, MissingInformation

SWITCH_TYPE = SwitchEntityDescription(
    key="switch",
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vegetronix sensors from a config entry."""
    # Assuming we have a list of sensor data from the device
    sensors = []
    num_sensors = int(config_entry.data.get("hub", {}).get("num_channels") or 0)
    num_actuators = int(config_entry.data.get("hub", {}).get("num_actuators") or 0)
    is_ac = int(config_entry.data.get("hub", {}).get("is_ac") or 0)

    num_batteries = 1
    if is_ac:
        num_batteries = 0

    _LOGGER.info("Adding %s actuators", num_actuators)

    # We add up the number of sensors, plus the number of actuators, then add one
    # for battery reading, and one because the array is 1 based instead of 0 based.
    for i in range(
        num_sensors + 1, num_sensors + num_actuators + 1
    ):  # Add 1 for battery
        if i > num_sensors:
            name = f"VegeHub Actuator {i - num_sensors}"
            _LOGGER.info("Setting up %s", name)
            sensor = VegeHubSwitch(
                name=name,
                sens_slot=i + num_batteries,
                act_slot=i - num_sensors - 1,
                config_entry=config_entry,
            )
            _LOGGER.info("Sensor id %s", sensor.unique_id)

            # Store the entity by ID in hass.data
            # if sensor.unique_id not in hass.data[DOMAIN]:
            hass.data[DOMAIN][sensor.unique_id] = sensor

            sensors.append(sensor)

    if sensors:
        async_add_entities(sensors)


class VegeHubSwitch(SwitchEntity):
    """Class for VegeHub Binary Sensors."""

    def __init__(self, name, sens_slot, act_slot, config_entry) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry

        new_id = (
            f"vegehub_{self.mac_addr}_{sens_slot}".lower()
        )  # Generate a unique_id using mac and slot

        self._attr_name: str = name
        self._state = None  # assuming 'v' is the latest sensor value
        self._sens_slot = sens_slot
        self._act_slot = act_slot
        self._attr_unique_id: str = new_id
        self.entity_id = "switch." + new_id
        self.entity_description: SwitchEntityDescription = SWITCH_TYPE

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return the class of this sensor."""
        return SwitchDeviceClass.SWITCH

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return UnitOfElectricPotential.VOLT

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._attr_unique_id

    @property
    def mac_addr(self) -> str:
        """Return the unique ID for this entity."""
        return self._config_entry.data.get("mac_address")

    @property
    def ip_addr(self) -> str:
        """Return the unique ID for this entity."""
        return self._config_entry.data.get("ip_addr")

    @property
    def is_on(self) -> bool:
        """Return true if actuator is on."""
        if self._state is not None:
            return self._state > 0
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.mac_addr)},
            name=self._config_entry.data.get("hostname"),
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def user_duration(self):
        """Retrieve the user duration from the options."""

        return int(self._config_entry.options.get("user_act_duration", 0) or 600)

    async def async_update_sensor(self, value):
        """Update the sensor state with the latest value."""
        self._state = value
        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # self.data.smartplug.state = "ON"
        _LOGGER.info("Switch ON")
        # self.hass.async_create_task(self._set_actuator(1))
        self.hass.add_job(self._set_actuator, 1)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # self.data.smartplug.state = "OFF"
        _LOGGER.info("Switch OFF")
        # self.hass.async_create_task(self._set_actuator(0))
        self.hass.add_job(self._set_actuator, 0)

    def update(self) -> None:
        """Get the latest data from the smart plug and updates the states."""
        # self.data.update()
        _LOGGER.info("Switch Update")
        # /api/actuators/status

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # return self.data.available

        # snick - Maybe we just have this ping the hub and see if it's there. If not, return false and the actuator isn't available?
        return True

    async def _set_actuator(self, state):
        url = f"http://{self.ip_addr}/api/actuators/set"
        _LOGGER.info("Setting actuator %s on %s", self._act_slot, self.ip_addr)

        # Prepare the JSON payload for the POST request
        payload = {
            "target": self._act_slot,
            "duration": self.user_duration,
            "state": state,
        }

        # Use aiohttp to send the POST request with the JSON body
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=payload) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "Failed to set actuator state on %s: HTTP %s",
                    url,
                    response.status,
                )
                raise CommunicationFailed

    async def _get_actuator_info(self, ip_address):
        """Fetch the current status of the actuators. Incomplete function, but not sure if we need it."""
        url = f"http://{ip_address}/api/actuators/status"
        _LOGGER.info("Retrieving MAC address from %s", ip_address)

        # Use aiohttp to send the POST request with the JSON body
        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status != 200:
                _LOGGER.error(
                    "Failed to get config from %s: HTTP %s", url, response.status
                )
                raise CommunicationFailed

            # Parse the JSON response
            config_data = await response.json()
            mac_address = config_data.get("wifi", {}).get("mac_addr")
            if not mac_address:
                _LOGGER.error(
                    "MAC address not found in the config response from %s", ip_address
                )
                raise MissingInformation
            simplified_mac_address = mac_address.replace(":", "")
            _LOGGER.info("%s MAC address: %s", ip_address, mac_address)
            return simplified_mac_address
