"""Support for Ecovacs Deebot vacuums."""

from sucks import VacBot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_OVERRIDE_REST_URL, DOMAIN
from .controller import EcovacsController
from .services import async_setup_services
from .util import get_client_device_id

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]
type EcovacsConfigEntry = ConfigEntry[EcovacsController]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EcovacsConfigEntry) -> bool:
    """Set up this integration using UI."""
    controller = EcovacsController(hass, entry.data)

    entry.async_on_unload(controller.teardown)

    await controller.initialize()

    entry.runtime_data = controller

    async def _async_wait_connect(device: VacBot) -> None:
        await hass.async_add_executor_job(device.connect_and_wait_until_ready)

    for device in controller.legacy_devices:
        entry.async_create_background_task(
            hass=hass,
            target=_async_wait_connect(device),
            name=f"{entry.title}_wait_connect_{device.vacuum['did']}",
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcovacsConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: EcovacsConfigEntry) -> bool:
    """Migrate an old entry."""
    if entry.version == 1 and entry.minor_version < 2:
        # Persist the client device ID, which was generated on every start before
        rest_url = entry.data.get(CONF_OVERRIDE_REST_URL)
        device_id = get_client_device_id(hass, rest_url is not None, entry.data)
        hass.config_entries.async_update_entry(
            entry,
            data=entry.data | {CONF_DEVICE_ID: device_id},
            minor_version=2,
        )

    return True
