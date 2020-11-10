"""Shelly entity helper."""
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

import aioshelly

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers import device_registry, entity

from . import ShellyDeviceWrapper
from .const import DATA_CONFIG_ENTRY, DOMAIN


def temperature_unit(block_info: dict) -> str:
    """Detect temperature unit."""
    if block_info[aioshelly.BLOCK_VALUE_UNIT] == "F":
        return TEMP_FAHRENHEIT
    return TEMP_CELSIUS


def shelly_naming(self, block, entity_type: str):
    """Naming for switch and sensors."""

    entity_name = self.wrapper.name
    if not block:
        return f"{entity_name} {self.description.name}"

    channels = 0
    mode = block.type + "s"
    if "num_outputs" in self.wrapper.device.shelly:
        channels = self.wrapper.device.shelly["num_outputs"]
        if (
            self.wrapper.model in ["SHSW-21", "SHSW-25"]
            and self.wrapper.device.settings["mode"] == "roller"
        ):
            channels = 1
        if block.type == "emeter" and "num_emeters" in self.wrapper.device.shelly:
            channels = self.wrapper.device.shelly["num_emeters"]
    if channels > 1 and block.type != "device":
        # Shelly EM (SHEM) with firmware v1.8.1 doesn't have "name" key; will be fixed in next firmware release
        if "name" in self.wrapper.device.settings[mode][int(block.channel)]:
            entity_name = self.wrapper.device.settings[mode][int(block.channel)]["name"]
        else:
            entity_name = None
        if not entity_name:
            if self.wrapper.model == "SHEM-3":
                base = ord("A")
            else:
                base = ord("1")
            entity_name = f"{self.wrapper.name} channel {chr(int(block.channel)+base)}"

    if entity_type == "switch":
        return entity_name

    if entity_type == "sensor":
        return f"{entity_name} {self.description.name}"

    raise ValueError


async def async_setup_entry_attribute_entities(
    hass, config_entry, async_add_entities, sensors, sensor_class
):
    """Set up entities for block attributes."""
    wrapper: ShellyDeviceWrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ]
    blocks = []

    for block in wrapper.device.blocks:
        for sensor_id in block.sensor_ids:
            description = sensors.get((block.type, sensor_id))
            if description is None:
                continue

            # Filter out non-existing sensors and sensors without a value
            if getattr(block, sensor_id, None) in (-1, None):
                continue

            blocks.append((block, sensor_id, description))

    if not blocks:
        return

    counts = Counter([item[1] for item in blocks])

    async_add_entities(
        [
            sensor_class(wrapper, block, sensor_id, description, counts[sensor_id])
            for block, sensor_id, description in blocks
        ]
    )


@dataclass
class BlockAttributeDescription:
    """Class to describe a sensor."""

    name: str
    # Callable = lambda attr_info: unit
    unit: Union[None, str, Callable[[dict], str]] = None
    value: Callable[[Any], Any] = lambda val: val
    device_class: Optional[str] = None
    default_enabled: bool = True
    available: Optional[Callable[[aioshelly.Block], bool]] = None
    device_state_attributes: Optional[
        Callable[[aioshelly.Block], Optional[dict]]
    ] = None


class ShellyBlockEntity(entity.Entity):
    """Helper class to represent a block."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block):
        """Initialize Shelly entity."""
        self.wrapper = wrapper
        self.block = block
        self._name = shelly_naming(self, block, "switch")

    @property
    def name(self):
        """Name of entity."""
        return self._name

    @property
    def should_poll(self):
        """If device should be polled."""
        return False

    @property
    def device_info(self):
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def available(self):
        """Available."""
        return self.wrapper.last_update_success

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.block.description}"

    async def async_added_to_hass(self):
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self):
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self):
        """Handle device update."""
        self.async_write_ha_state()


class ShellyBlockAttributeEntity(ShellyBlockEntity, entity.Entity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(
        self,
        wrapper: ShellyDeviceWrapper,
        block: aioshelly.Block,
        attribute: str,
        description: BlockAttributeDescription,
        same_type_count: int,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper, block)
        self.attribute = attribute
        self.description = description
        self.info = block.info(attribute)

        unit = self.description.unit

        if callable(unit):
            unit = unit(self.info)

        self._unit = unit
        self._unique_id = f"{super().unique_id}-{self.attribute}"
        self._name = shelly_naming(self, block, "sensor")

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def name(self):
        """Name of sensor."""
        return self._name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if it should be enabled by default."""
        return self.description.default_enabled

    @property
    def attribute_value(self):
        """Value of sensor."""
        value = getattr(self.block, self.attribute)

        if value is None:
            return None

        return self.description.value(value)

    @property
    def unit_of_measurement(self):
        """Return unit of sensor."""
        return self._unit

    @property
    def device_class(self):
        """Device class of sensor."""
        return self.description.device_class

    @property
    def available(self):
        """Available."""
        available = super().available

        if not available or not self.description.available:
            return available

        return self.description.available(self.block)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.description.device_state_attributes is None:
            return None

        return self.description.device_state_attributes(self.block)
