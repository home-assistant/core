"""The ONVIF integration."""
from onvif.exceptions import ONVIFAuthError, ONVIFError, ONVIFTimeoutError

from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.components.stream import CONF_RTSP_TRANSPORT, RTSP_TRANSPORTS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SNAPSHOT_AUTH, DEFAULT_ARGUMENTS, DOMAIN
from .device import ONVIFDevice


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ONVIF from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not entry.options:
        await async_populate_options(hass, entry)

    device = ONVIFDevice(hass, entry)

    if not await device.async_setup():
        await device.device.close()
        return False

    if not device.available:
        raise ConfigEntryNotReady()

    if not entry.data.get(CONF_SNAPSHOT_AUTH):
        await async_populate_snapshot_auth(hass, device, entry)

    hass.data[DOMAIN][entry.unique_id] = device

    platforms = [Platform.BUTTON, Platform.CAMERA]

    if device.capabilities.events:
        platforms += [Platform.BINARY_SENSOR, Platform.SENSOR]

    if device.capabilities.imaging:
        platforms += [Platform.SWITCH]

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.async_stop)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    device = hass.data[DOMAIN][entry.unique_id]
    platforms = ["camera"]

    if device.capabilities.events and device.events.started:
        platforms += [Platform.BINARY_SENSOR, Platform.SENSOR]
        await device.events.async_stop()
    if device.capabilities.imaging:
        platforms += [Platform.SWITCH]

    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def _get_snapshot_auth(device):
    """Determine auth type for snapshots."""
    if not device.capabilities.snapshot or not (device.username and device.password):
        return HTTP_DIGEST_AUTHENTICATION

    try:
        snapshot = await device.device.get_snapshot(device.profiles[0].token)

        if snapshot:
            return HTTP_DIGEST_AUTHENTICATION
        return HTTP_BASIC_AUTHENTICATION
    except (ONVIFAuthError, ONVIFTimeoutError):
        return HTTP_BASIC_AUTHENTICATION
    except ONVIFError:
        return HTTP_DIGEST_AUTHENTICATION


async def async_populate_snapshot_auth(hass, device, entry):
    """Check if digest auth for snapshots is possible."""
    auth = await _get_snapshot_auth(device)
    new_data = {**entry.data, CONF_SNAPSHOT_AUTH: auth}
    hass.config_entries.async_update_entry(entry, data=new_data)


async def async_populate_options(hass, entry):
    """Populate default options for device."""
    options = {
        CONF_EXTRA_ARGUMENTS: DEFAULT_ARGUMENTS,
        CONF_RTSP_TRANSPORT: next(iter(RTSP_TRANSPORTS)),
    }

    hass.config_entries.async_update_entry(entry, options=options)
