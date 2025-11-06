"""Support for Satel Integra zone states- represented as binary sensors."""

from __future__ import annotations

from satel_integra.satel_integra import AsyncSatel

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_OUTPUT_NUMBER,
    CONF_OUTPUTS,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_ZONES_UPDATED,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
    SatelConfigEntry,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra binary sensor devices."""

    controller = config_entry.runtime_data

    zone_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_ZONE,
        config_entry.subentries.values(),
    )

    for subentry in zone_subentries:
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]
        zone_type: BinarySensorDeviceClass = subentry.data[CONF_ZONE_TYPE]
        zone_name: str = subentry.data[CONF_NAME]

        async_add_entities(
            [
                SatelIntegraBinarySensor(
                    controller,
                    zone_num,
                    zone_name,
                    zone_type,
                    CONF_ZONES,
                    SIGNAL_ZONES_UPDATED,
                    config_entry.entry_id,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )

    output_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_OUTPUT,
        config_entry.subentries.values(),
    )

    for subentry in output_subentries:
        output_num: int = subentry.data[CONF_OUTPUT_NUMBER]
        ouput_type: BinarySensorDeviceClass = subentry.data[CONF_ZONE_TYPE]
        output_name: str = subentry.data[CONF_NAME]

        async_add_entities(
            [
                SatelIntegraBinarySensor(
                    controller,
                    output_num,
                    output_name,
                    ouput_type,
                    CONF_OUTPUTS,
                    SIGNAL_OUTPUTS_UPDATED,
                    config_entry.entry_id,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraBinarySensor(BinarySensorEntity):
    """Representation of an Satel Integra binary sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        controller: AsyncSatel,
        device_number: int,
        device_name: str,
        device_class: BinarySensorDeviceClass,
        sensor_type: str,
        react_to_signal: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the binary_sensor."""
        self._device_number = device_number
        self._attr_unique_id = f"{config_entry_id}_{sensor_type}_{device_number}"
        self._state: int = 0
        self._react_to_signal = react_to_signal
        self._satel = controller

        self._attr_name = device_name
        self._attr_device_class = device_class

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._react_to_signal == SIGNAL_OUTPUTS_UPDATED:
            self._state = (
                1 if self._device_number in self._satel.violated_outputs else 0
            )
        else:
            self._state = 1 if self._device_number in self._satel.violated_zones else 0

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._react_to_signal, self._devices_updated
            )
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._state == 1

    @callback
    def _devices_updated(self, zones: dict[int, int]):
        """Update the zone's state, if needed."""
        if self._device_number in zones and self._state != zones[self._device_number]:
            self._state = zones[self._device_number]
            self.async_write_ha_state()
