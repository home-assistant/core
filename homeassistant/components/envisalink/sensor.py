"""Support for Envisalink sensors (shows panel info)."""

import logging
from typing import Any, override

from pyenvisalink import EnvisalinkAlarmPanel

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnvisalinkConfigEntry
from .const import (
    CONF_PARTITION_NUMBER,
    CONF_PARTITIONNAME,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    SUBENTRY_TYPE_PARTITION,
)
from .entity import EnvisalinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnvisalinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Envisalink sensor entities from a config entry."""
    controller = entry.runtime_data

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PARTITION):
        partition_number = subentry.data[CONF_PARTITION_NUMBER]
        entity = EnvisalinkSensor(
            subentry.data[CONF_PARTITIONNAME],
            partition_number,
            controller.alarm_state["partition"][partition_number],
            controller,
        )
        async_add_entities([entity], config_subentry_id=subentry.subentry_id)


class EnvisalinkSensor(EnvisalinkEntity, SensorEntity):
    """Representation of an Envisalink keypad."""

    _attr_icon = "mdi:message-text"

    def __init__(
        self,
        partition_name: str,
        partition_number: int,
        info: dict[str, Any],
        controller: EnvisalinkAlarmPanel,
    ) -> None:
        """Initialize the sensor."""
        self._partition_number = partition_number

        _LOGGER.debug("Setting up sensor for partition: %s", partition_name)
        super().__init__(f"{partition_name} Keypad", info, controller)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_KEYPAD_UPDATE, self.async_update_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PARTITION_UPDATE, self.async_update_callback
            )
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return the overall state."""
        return self._info["status"]["alpha"]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._info["status"]

    @callback
    def async_update_callback(self, partition):
        """Update the partition state in HA, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.async_write_ha_state()
