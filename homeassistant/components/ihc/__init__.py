"""Support for IHC devices."""
import logging

from ihcsdk.ihccontroller import IHCController

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .auto_setup import autosetup_ihc_products
from .const import CONF_AUTOSETUP, DOMAIN, IHC_CONTROLLER, IHC_PLATFORMS
from .manual_setup import manual_setup
from .migrate import migrate_configuration
from .service_functions import setup_service_functions

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IHC integration."""
    if config.get(DOMAIN) is not None:
        _LOGGER.error(
            """
            Setup of the IHC controller in configuration.yaml is no longer
            supported. See https://www.home-assistant.io/integrations/ihc/
            """
        )
        migrate_configuration(hass)
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the IHC Controller from a config entry."""
    controller_id: str = str(entry.unique_id)
    url: str = entry.data[CONF_URL]
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    autosetup: bool = entry.data[CONF_AUTOSETUP]
    ihc_controller: IHCController = IHCController(url, username, password)
    if not await hass.async_add_executor_job(ihc_controller.authenticate):
        _LOGGER.error("Unable to authenticate on IHC controller")
        return False
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][controller_id] = {
        IHC_CONTROLLER: ihc_controller,
    }
    if not await setup_controller_device(hass, ihc_controller, entry):
        return False
    if autosetup:
        await hass.async_add_executor_job(
            autosetup_ihc_products, hass, ihc_controller, controller_id
        )
    await hass.async_add_executor_job(manual_setup, hass, controller_id)
    for component in IHC_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    entry.add_update_listener(async_update_options)
    # We only wan to register service functions once, in case you have multiple controllers
    if len(hass.data[DOMAIN]) == 1:
        setup_service_functions(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, IHC_PLATFORMS
    )
    if not unload_ok:
        return False
    controller_id = config_entry.unique_id
    ihc_controller = hass.data[DOMAIN][controller_id][IHC_CONTROLLER]
    ihc_controller.disconnect()
    hass.data[DOMAIN].pop(controller_id)
    if hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def setup_controller_device(
    hass: HomeAssistant, ihc_controller: IHCController, entry: ConfigEntry
) -> bool:
    """Register the IHC controller as a Home Assistant device."""
    # We must have a controller id, and cast the unique_id to a string.
    # we know it is not None because it will always be set to the controller serial during setup
    controller_id: str = str(entry.unique_id)
    system_info = await hass.async_add_executor_job(
        ihc_controller.client.get_system_info
    )
    if not system_info:
        _LOGGER.error("Unable to get system information from IHC controller")
        return False
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller_id)},
        name=system_info["serial_number"],
        manufacturer="Schneider Electric",
        model=f"{system_info['brand']} {system_info['hw_revision']}",
        sw_version=system_info["version"],
    )
    return True
