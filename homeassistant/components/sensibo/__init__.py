"""The Sensibo component."""

from pysensibo.exceptions import AuthenticationError

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import SensiboDataUpdateCoordinator
from .entity import get_device_info
from .services import async_setup_services
from .util import NoDevicesError, NoUsernameError, async_validate_api

type SensiboConfigEntry = ConfigEntry[SensiboDataUpdateCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sensibo component."""
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SensiboConfigEntry) -> bool:
    """Set up Sensibo from a config entry."""

    coordinator = SensiboDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)

    def _async_register_devices() -> None:
        """Register parent AC devices so motion sensors can resolve via_device_id.

        Registered before the platforms so it runs first on every coordinator
        update, ensuring a parent device exists before the (concurrently set up)
        motion sensors resolve it, including devices added dynamically at runtime.
        """
        for device in coordinator.data.parsed.values():
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id, **get_device_info(device)
            )

    _async_register_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_register_devices))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SensiboConfigEntry) -> bool:
    """Unload Sensibo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SensiboConfigEntry) -> bool:
    """Migrate old entry."""
    # Change entry unique id from api_key to username
    if entry.version == 1:
        api_key = entry.data[CONF_API_KEY]

        try:
            new_unique_id = await async_validate_api(hass, api_key)
        except AuthenticationError, ConnectionError, NoDevicesError, NoUsernameError:
            return False

        LOGGER.debug("Migrate Sensibo config entry unique id to %s", new_unique_id)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=new_unique_id,
            version=2,
        )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: SensiboConfigEntry, device: AnyDeviceEntry
) -> bool:
    """Remove Sensibo config entry from a device."""
    entity_registry = er.async_get(hass)
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN and entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, identifier[1]
        ):
            return False

    return True
