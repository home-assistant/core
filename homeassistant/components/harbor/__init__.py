"""The Harbor integration."""

from harbor.config import HarborCameraConfig

from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_CERT_PEM, CONF_KEY_PEM, CONF_SERIAL, DOMAIN, PLATFORMS
from .coordinator import HarborConfigEntry, HarborCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: HarborConfigEntry) -> bool:
    """Set up Harbor from a config entry."""
    coordinator = HarborCoordinator(
        hass,
        entry,
        HarborCameraConfig(
            serial=entry.data[CONF_SERIAL],
            cert_pem=entry.data[CONF_CERT_PEM],
            key_pem=entry.data[CONF_KEY_PEM],
            ip_address=entry.data[CONF_IP_ADDRESS],
        ),
    )
    await coordinator.async_start()
    try:
        await coordinator.async_wait_until_ready()
    except TimeoutError as err:
        await coordinator.async_shutdown()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HarborConfigEntry) -> bool:
    """Unload a Harbor config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unload_ok
