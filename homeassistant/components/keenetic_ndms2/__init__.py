"""The keenetic_ndms2 component."""

from homeassistant.components import binary_sensor, device_tracker
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant

from .const import DOMAIN
from .router import KeeneticRouter


async def async_setup(hass: HomeAssistant, _config: Config) -> bool:
    """Set up configured entries."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the component."""

    router = KeeneticRouter(hass, config_entry)
    await router.async_setup()

    hass.data[DOMAIN][config_entry.entry_id] = router
    for component in [device_tracker.DOMAIN, binary_sensor.DOMAIN]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for component in [device_tracker.DOMAIN, binary_sensor.DOMAIN]:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)

    router: KeeneticRouter = hass.data[DOMAIN].pop(config_entry.entry_id)

    await router.async_teardown()

    return True
