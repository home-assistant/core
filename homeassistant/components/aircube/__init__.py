"""The airCube component."""
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_MANUFACTURER,
    CONF_DETECTION_TIME,
    DEFAULT_DETECTION_TIME,
    DEFAULT_NAME,
    DOMAIN,
)
from .router import AirCubeRouter

AIRCUBE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
            vol.Optional(
                CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME
            ): cv.time_period,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [AIRCUBE_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Import the airCube component from config."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the airCube component."""
    router = AirCubeRouter(hass, config_entry)
    if not await router.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = router
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, router.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=router.model,
        name=router.hostname,
        sw_version=router.firmware,
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True
