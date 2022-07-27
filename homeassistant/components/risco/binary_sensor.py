"""Support for Risco alarm zones."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import is_local
from .const import DATA_COORDINATOR, DOMAIN, SYSTEM, ZONE_UPDATES
from .entity import RiscoEntity, binary_sensor_unique_id

SERVICE_BYPASS_ZONE = "bypass_zone"
SERVICE_UNBYPASS_ZONE = "unbypass_zone"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Risco alarm control panel."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_BYPASS_ZONE, {}, "async_bypass_zone")
    platform.async_register_entity_service(
        SERVICE_UNBYPASS_ZONE, {}, "async_unbypass_zone"
    )

    if is_local(config_entry):
        zone_updates = hass.data[DOMAIN][config_entry.entry_id][ZONE_UPDATES]
        system = hass.data[DOMAIN][config_entry.entry_id][SYSTEM]
        local_entities = [
            RiscoLocalBinarySensor(system.id, zone_id, zone, zone_updates)
            for zone_id, zone in system.zones.items()
        ]
        async_add_entities(local_entities, False)
    else:
        coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
        cloud_entities = [
            RiscoCloudBinarySensor(coordinator, zone_id, zone)
            for zone_id, zone in coordinator.data.zones.items()
        ]
        async_add_entities(cloud_entities, False)


class RiscoBinarySensor(BinarySensorEntity):
    """Representation of a Risco zone as a binary sensor."""

    def __init__(self, zone_id, zone):
        """Init the zone."""
        self._zone_id = zone_id
        self._zone = zone

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Risco",
            name=self.name,
        )

    @property
    def unique_id(self) -> str:
        """Return a unique id for this zone."""
        raise NotImplementedError

    @property
    def name(self):
        """Return the name of the zone."""
        return self._zone.name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"zone_id": self._zone_id, "bypassed": self._zone.bypassed}

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._zone.triggered

    @property
    def device_class(self):
        """Return the class of this sensor, from BinarySensorDeviceClass."""
        return BinarySensorDeviceClass.MOTION

    async def async_bypass_zone(self):
        """Bypass this zone."""
        await self._bypass(True)

    async def async_unbypass_zone(self):
        """Unbypass this zone."""
        await self._bypass(False)

    async def _bypass(self, bypass):
        raise NotImplementedError


class RiscoCloudBinarySensor(RiscoEntity, RiscoBinarySensor):
    """Representation of a Risco cloud zone as a binary sensor."""

    def __init__(self, coordinator, zone_id, zone):
        """Init the zone."""
        RiscoEntity.__init__(self, coordinator)
        RiscoBinarySensor.__init__(self, zone_id, zone)

    def _get_data_from_coordinator(self):
        self._zone = self.coordinator.data.zones[self._zone_id]

    @property
    def unique_id(self):
        """Return a unique id for this zone."""
        return binary_sensor_unique_id(self._risco, self._zone_id)

    async def _bypass(self, bypass):
        alarm = await self._risco.bypass_zone(self._zone_id, bypass)
        self._zone = alarm.zones[self._zone_id]
        self.async_write_ha_state()


class RiscoLocalBinarySensor(RiscoBinarySensor):
    """Representation of a Risco local zone as a binary sensor."""

    def __init__(self, system_id, zone_id, zone, zone_updates):
        """Init the zone."""
        super().__init__(zone_id, zone)
        self._system_id = system_id
        self._zone_updates = zone_updates

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._zone_updates[self._zone_id] = self.async_write_ha_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            **super().extra_state_attributes,
            "alarmed": self._zone.alarmed,
            "groups": self._zone.groups,
        }

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self):
        """Return a unique id for this zone."""
        return f"{self._system_id}_zone_{self._zone_id}_local"

    async def _bypass(self, bypass):
        await self._zone.bypass(bypass)
