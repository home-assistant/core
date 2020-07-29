"""The keenetic_ndms2 component."""

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
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, router.host)},
        manufacturer=router.manufacturer,
        model=router.model,
        name=router.name,
        sw_version=router.firmware,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")

    router: KeeneticRouter = hass.data[DOMAIN].pop(config_entry.entry_id)

    await router.async_teardown()

    return True
