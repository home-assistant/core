"""The ONVIF integration."""
import logging

from httpx import RequestError
from onvif.exceptions import ONVIFAuthError, ONVIFError, ONVIFTimeoutError
from zeep.exceptions import Fault, TransportError

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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_SNAPSHOT_AUTH, DEFAULT_ARGUMENTS, DOMAIN
from .device import ONVIFDevice
from .util import is_auth_error, stringify_onvif_error

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ONVIF from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not entry.options:
        await async_populate_options(hass, entry)

    device = ONVIFDevice(hass, entry)

    try:
        await device.async_setup()
        if not entry.data.get(CONF_SNAPSHOT_AUTH):
            await async_populate_snapshot_auth(hass, device, entry)
    except RequestError as err:
        await device.device.close()
        raise ConfigEntryNotReady(
            f"Could not connect to camera {device.device.host}:{device.device.port}: {err}"
        ) from err
    except Fault as err:
        await device.device.close()
        if is_auth_error(err):
            raise ConfigEntryAuthFailed(
                f"Auth Failed: {stringify_onvif_error(err)}"
            ) from err
        raise ConfigEntryNotReady(
            f"Could not connect to camera: {stringify_onvif_error(err)}"
        ) from err
    except ONVIFError as err:
        await device.device.close()
        raise ConfigEntryNotReady(
            f"Could not setup camera {device.device.host}:{device.device.port}: {err}"
        ) from err

    if not device.available:
        raise ConfigEntryNotReady()

    hass.data[DOMAIN][entry.unique_id] = device

    device.platforms = [Platform.BUTTON, Platform.CAMERA]

    if device.capabilities.events:
        device.platforms += [Platform.BINARY_SENSOR, Platform.SENSOR]

    if device.capabilities.imaging:
        device.platforms += [Platform.SWITCH]

    await hass.config_entries.async_forward_entry_setups(entry, device.platforms)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.async_stop)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    device: ONVIFDevice = hass.data[DOMAIN][entry.unique_id]

    if device.capabilities.events and device.events.started:
        try:
            await device.events.async_stop()
        except (ONVIFError, Fault, RequestError, TransportError):
            LOGGER.warning("Error while stopping events: %s", device.name)

    return await hass.config_entries.async_unload_platforms(entry, device.platforms)


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
