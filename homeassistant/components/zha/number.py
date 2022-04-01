"""Support for ZHA AnalogOutput cluster."""
import functools
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CHANNEL_ANALOG_OUTPUT,
    DATA_ZHA,
    ICONS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    UNITS,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.NUMBER)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation Analog Output from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.NUMBER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
            update_before_add=False,
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(channel_names=CHANNEL_ANALOG_OUTPUT)
class ZhaNumber(ZhaEntity, NumberEntity):
    """Representation of a ZHA Number entity."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this entity."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._analog_output_channel = self.cluster_channels.get(CHANNEL_ANALOG_OUTPUT)

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._analog_output_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def value(self):
        """Return the current value."""
        return self._analog_output_channel.present_value

    @property
    def min_value(self):
        """Return the minimum value."""
        min_present_value = self._analog_output_channel.min_present_value
        if min_present_value is not None:
            return min_present_value
        return 0

    @property
    def max_value(self):
        """Return the maximum value."""
        max_present_value = self._analog_output_channel.max_present_value
        if max_present_value is not None:
            return max_present_value
        return 1023

    @property
    def step(self):
        """Return the value step."""
        resolution = self._analog_output_channel.resolution
        if resolution is not None:
            return resolution
        return super().step

    @property
    def name(self):
        """Return the name of the number entity."""
        description = self._analog_output_channel.description
        if description is not None and len(description) > 0:
            return f"{super().name} {description}"
        return super().name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        application_type = self._analog_output_channel.application_type
        if application_type is not None:
            return ICONS.get(application_type >> 16, super().icon)
        return super().icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        engineering_units = self._analog_output_channel.engineering_units
        return UNITS.get(engineering_units)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle value update from channel."""
        self.async_write_ha_state()

    async def async_set_value(self, value):
        """Update the current value from HA."""
        num_value = float(value)
        if await self._analog_output_channel.async_set_present_value(num_value):
            self.async_write_ha_state()

    async def async_update(self):
        """Attempt to retrieve the state of the entity."""
        await super().async_update()
        _LOGGER.debug("polling current state")
        if self._analog_output_channel:
            value = await self._analog_output_channel.get_attribute_value(
                "present_value", from_cache=False
            )
            _LOGGER.debug("read value=%s", value)
