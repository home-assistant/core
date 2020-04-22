"""Support for getting probe data from Neptune Apex."""
import logging

import pynepsys

from homeassistant.helpers.entity import Entity

from . import NEPTUNE_APEX, NEPTUNE_APEX_COORDINATOR

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:thermometer-lines"


async def async_setup_entry(hass, entry, async_add_entities):
    """Parse through the Apex probes and creates Probe entities."""
    apex = hass.data[NEPTUNE_APEX]
    coordinator = hass.data[NEPTUNE_APEX_COORDINATOR]

    async_add_entities(
        Probe(coordinator, apex, name) for i, name in enumerate(coordinator.data.probes)
    )


class Probe(Entity):
    """Abstract representation of Apex probes."""

    def __init__(self, coordinator, apex: pynepsys.Apex, name):
        """Initialize this probe, storing reference to parent Apex."""
        self.coordinator = coordinator
        self._name = name
        self.probe = apex.probes[name]

    @property
    def unit_of_measurement(self):
        """Return the probe type."""
        return self.probe.type

    @property
    def device_class(self):
        """Return device type for temperature and power probes."""
        if self.probe_type == "Temp":
            return "temperature"
        if self.probe_type == "Amps":
            return "power"
        return None

    @property
    def probe_type(self):
        """Return the probe type."""
        return self.probe.type

    @property
    def state(self):
        """Return the current value of the probe."""
        return self.probe.value

    @property
    def name(self):
        """Name of this probe (From the Apex), prefixed."""
        return "apex." + self._name

    @property
    def unique_id(self):
        """Name of this probe as defined in the Apex."""
        return self.name

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
