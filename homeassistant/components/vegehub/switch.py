"""Switch configuration for VegeHub integration."""

from typing import Any

from vegehub import VegeHub

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

SWITCH_TYPE = SwitchEntityDescription(
    key="switch",
)


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

    # We add up the number of sensors, plus the number of actuators, then add one
    # for battery reading, and one because the array is 1 based instead of 0 based.
    for i in range(
        num_sensors + 1, num_sensors + num_actuators + 1
    ):  # Add 1 for battery
        if i > num_sensors:
            name = f"VegeHub Actuator {i - num_sensors}"
            sensor = VegeHubSwitch(
                name=name,
                sens_slot=i + num_batteries,
                act_slot=i - num_sensors - 1,
                config_entry=config_entry,
            )

            # Store the entity by ID in hass.data
            # if sensor.unique_id not in hass.data[DOMAIN]:
            hass.data[DOMAIN][sensor.unique_id] = sensor

            sensors.append(sensor)

    if sensors:
        async_add_entities(sensors)


class VegeHubSwitch(SwitchEntity):
    """Class for VegeHub Binary Sensors."""

    def __init__(self, name, sens_slot, act_slot, config_entry, state=None) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry

        new_id = (
            f"vegehub_{self.mac_addr}_{sens_slot}".lower()
        )  # Generate a unique_id using mac and slot

        self._attr_name: str = name
        self._state: float | None = state
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
    def user_duration(self) -> int:
        """Retrieve the user duration from the options."""
        return int(self._config_entry.options.get("user_act_duration", 0) or 600)

    async def async_update_sensor(self, value: float) -> None:
        """Update the sensor state with the latest value."""
        self._state = value
        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.hass.add_job(self._set_actuator, 1)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.hass.add_job(self._set_actuator, 0)

    def update(self) -> None:
        """Get the latest data from the smart plug and updates the states."""
        # May add functionality to update switch state, but it is already updated by
        # incoming hub communication whenever it changes.

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        # Maybe in the future have this ping the hub and see if it's there.
        # If not, return false and the actuator isn't available?
        return True

    async def _set_actuator(self, state: int) -> bool:
        """Set the actuator on the Hub to the desired state (1 or 0)."""
        hub = VegeHub(self.ip_addr)
        return await hub.set_actuator(state, self._act_slot, self.user_duration)
