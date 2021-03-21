"""A sensor that monitors for data anomalies in other components."""

from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "anomaly"
PLATFORMS = ["binary_sensor"]


async def async_setup(hass, config):
    """Set up the anomaly sensor platform."""
    hass.async_create_task(
        async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    )
    return True
