"""Support for Plaato devices."""

from datetime import timedelta
import logging

from aiohttp import web
from pyplaato.models.airlock import PlaatoAirlock
from pyplaato.plaato import (
    ATTR_ABV,
    ATTR_BATCH_VOLUME,
    ATTR_BPM,
    ATTR_BUBBLES,
    ATTR_CO2_VOLUME,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_NAME,
    ATTR_OG,
    ATTR_SG,
    ATTR_TEMP,
    ATTR_TEMP_UNIT,
    ATTR_VOLUME_UNIT,
)
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_USE_WEBHOOK,
    COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DEVICE,
    DEVICE_ID,
    DEVICE_NAME,
    DEVICE_TYPE,
    DOMAIN,
    PLATFORMS,
    SENSOR_DATA,
    UNDO_UPDATE_LISTENER,
)
from .coordinator import PlaatoCoordinator

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["webhook"]

SENSOR_UPDATE = f"{DOMAIN}_sensor_update"
SENSOR_DATA_KEY = f"{DOMAIN}.{SENSOR}"

WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.positive_int,
        vol.Required(ATTR_TEMP_UNIT): vol.In(
            [UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT]
        ),
        vol.Required(ATTR_VOLUME_UNIT): vol.In(
            [UnitOfVolume.LITERS, UnitOfVolume.GALLONS]
        ),
        vol.Required(ATTR_BPM): cv.positive_int,
        vol.Required(ATTR_TEMP): vol.Coerce(float),
        vol.Required(ATTR_SG): vol.Coerce(float),
        vol.Required(ATTR_OG): vol.Coerce(float),
        vol.Required(ATTR_ABV): vol.Coerce(float),
        vol.Required(ATTR_CO2_VOLUME): vol.Coerce(float),
        vol.Required(ATTR_BATCH_VOLUME): vol.Coerce(float),
        vol.Required(ATTR_BUBBLES): cv.positive_int,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure based on config entry."""
    hass.data.setdefault(DOMAIN, {})

    if entry.data[CONF_USE_WEBHOOK]:
        async_setup_webhook(hass, entry)
    else:
        await async_setup_coordinator(hass, entry)

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if entry.options.get(platform, True)]
    )

    return True


@callback
def async_setup_webhook(hass: HomeAssistant, entry: ConfigEntry):
    """Init webhook based on config entry."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    device_name = entry.data[CONF_DEVICE_NAME]

    _set_entry_data(entry, hass)

    webhook.async_register(
        hass, DOMAIN, f"{DOMAIN}.{device_name}", webhook_id, handle_webhook
    )


async def async_setup_coordinator(hass: HomeAssistant, entry: ConfigEntry):
    """Init auth token based on config entry."""
    auth_token = entry.data[CONF_TOKEN]
    device_type = entry.data[CONF_DEVICE_TYPE]

    if entry.options.get(CONF_SCAN_INTERVAL):
        update_interval = timedelta(minutes=entry.options[CONF_SCAN_INTERVAL])
    else:
        update_interval = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

    coordinator = PlaatoCoordinator(hass, auth_token, device_type, update_interval)
    await coordinator.async_config_entry_first_refresh()

    _set_entry_data(entry, hass, coordinator, auth_token)

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)


def _set_entry_data(entry, hass, coordinator=None, device_id=None):
    device = {
        DEVICE_NAME: entry.data[CONF_DEVICE_NAME],
        DEVICE_TYPE: entry.data[CONF_DEVICE_TYPE],
        DEVICE_ID: device_id,
    }

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        DEVICE: device,
        SENSOR_DATA: None,
        UNDO_UPDATE_LISTENER: entry.add_update_listener(_async_update_listener),
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    use_webhook = entry.data[CONF_USE_WEBHOOK]
    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if use_webhook:
        return await async_unload_webhook(hass, entry)

    return await async_unload_coordinator(hass, entry)


async def async_unload_webhook(hass: HomeAssistant, entry: ConfigEntry):
    """Unload webhook based entry."""
    if entry.data[CONF_WEBHOOK_ID] is not None:
        webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return await async_unload_platforms(hass, entry, PLATFORMS)


async def async_unload_coordinator(hass: HomeAssistant, entry: ConfigEntry):
    """Unload auth token based entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    return await async_unload_platforms(hass, entry, coordinator.platforms)


async def async_unload_platforms(hass: HomeAssistant, entry: ConfigEntry, platforms):
    """Unload platforms."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response | None:
    """Handle incoming webhook from Plaato."""
    try:
        data = WEBHOOK_SCHEMA(await request.json())
    except vol.MultipleInvalid as error:
        _LOGGER.warning("An error occurred when parsing webhook data <%s>", error)
        return None

    device_id = _device_id(data)
    sensor_data = PlaatoAirlock.from_web_hook(data)

    async_dispatcher_send(hass, SENSOR_UPDATE, *(device_id, sensor_data))

    return web.Response(text=f"Saving status for {device_id}")


def _device_id(data):
    """Return name of device sensor."""
    return f"{data.get(ATTR_DEVICE_NAME)}_{data.get(ATTR_DEVICE_ID)}"
