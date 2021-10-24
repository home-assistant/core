"""Initialize Salus integration."""
import logging

from salus.api import Api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import SalusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Salus from a config entry."""
    salus_api = await hass.async_add_executor_job(_get_salus_api_instance, entry)
    devices = await hass.async_add_executor_job(salus_api.get_devices)
    device = next(d for d in devices if d.device_id == entry.data[CONF_DEVICE])

    coordinator = SalusDataUpdateCoordinator(
        hass,
        api=salus_api,
        device_id=entry.data[CONF_DEVICE],
    )
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = (coordinator, device)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


def _get_salus_api_instance(entry: ConfigEntry) -> Api:
    """Initialize a new instance of SalusApi."""
    salus = Api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    return salus
