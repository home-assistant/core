"""Device tracker for AIS tracker."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MMSIS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for AIS tracker."""

    async_add_entities(AisTrackerEntity(mmsi) for mmsi in entry.data[CONF_MMSIS])


class AisTrackerEntity(TrackerEntity):
    """Represent a tracked device."""

    _attr_translation_key = "vessel"

    def __init__(self, mmsi: str) -> None:
        """Set up AIS tracker entity."""
        self._mmsi = mmsi
        self._attr_unique_id = f"ais_mmsi_{mmsi}_vessel"
        self._attr_name = mmsi
        self._attr_extra_state_attributes = {}
        self._latitude: float | None = None
        self._longitude: float | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(identifiers={(DOMAIN, self._mmsi)})

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._longitude

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    async def async_update_data_from_msg(self, event: Event) -> None:
        """Update data from received message."""
        msg = event.data
        if msg.get("msg_type") in [1, 2, 3]:  # position reports
            self._latitude = msg.get("lat")
            self._longitude = msg.get("lon")

        if msg.get("msg_type") == 5:  # Static and voyage related data
            self._attr_extra_state_attributes["shipname"] = msg.get("shipname")
            self._attr_extra_state_attributes["callsign"] = msg.get("callsign")

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for updates."""
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_{self._mmsi}", self.async_update_data_from_msg
            )
        )
