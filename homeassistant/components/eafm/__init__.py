"""UK Environment Agency Flood Monitoring Integration."""

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .station import Station


async def async_setup(hass, config):
    """Set up devices."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass, entry):
    """Set up flood monitoring sensors for this config entry."""
    station_key = entry.data["station"]

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "station-id", station_key)},
        name=entry.title,
        manufacturer="https://environment.data.gov.uk/",
        model="Real Time flood-monitoring API",
        entry_type="service",
    )

    station = hass.data[DOMAIN][station_key] = Station(hass, entry)
    hass.async_create_task(station.async_start())

    return True


async def async_unload_entry(hass, config_entry):
    """Unload flood monitoring sensors."""
    station_key = config_entry.data["station"]

    if station_key in hass.data[DOMAIN]:
        station = hass.data[DOMAIN][station_key]
        await station.async_stop()
        del hass.data[DOMAIN][station_key]

    return True
