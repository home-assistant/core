"""The MELCloud Climate integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Dict, List, Optional

from aiohttp import ClientConnectionError
from async_timeout import timeout
from pymelcloud import Client, Device
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_TOKEN
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORMS = ["climate", "sensor"]

CONF_LANGUAGE = "language"
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_TOKEN): str})}, extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigEntry):
    """Establish connection with MELCloud."""
    if DOMAIN not in config:
        return True

    email = config[DOMAIN].get(CONF_EMAIL)
    token = config[DOMAIN].get(CONF_TOKEN)
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_EMAIL: email, CONF_TOKEN: token},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Establish connection with MELClooud."""
    conf = entry.data
    mel_api = await mel_api_setup(hass, conf[CONF_TOKEN])
    if not mel_api:
        return False
    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: mel_api})
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await asyncio.wait(
        [
            hass.config_entries.async_forward_entry_unload(config_entry, platform)
            for platform in PLATFORMS
        ]
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True


class MelCloudDevice:
    """MELCloud Device instance."""

    def __init__(self, device: Device):
        """Construct a device wrapper."""
        self.device = device
        self.name = device.name
        self._available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Pull the latest data from MELCloud."""
        try:
            await self.device.update()
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False

    async def async_set(self, properties: Dict[str, any]):
        """Write state changes to the MELCloud API."""
        try:
            await self.device.set(properties)
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_id(self):
        """Return device ID."""
        return self.device.device_id

    @property
    def building_id(self):
        """Return building ID of the device."""
        return self.device.building_id

    @property
    def device_info(self):
        """Return a device description for device registry."""
        _device_info = {
            "identifiers": {(DOMAIN, f"{self.device.mac}-{self.device.serial}")},
            "manufacturer": "Mitsubishi Electric",
            "name": self.name,
        }
        unit_infos = self.device.units
        if unit_infos is not None:
            _device_info["model"] = ", ".join(
                list(set(map(lambda x: x["model"], unit_infos)))
            )
        return _device_info


async def mel_api_setup(hass, token) -> Optional[List[MelCloudDevice]]:
    """Create a MELCloud instance only once."""
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    try:
        with timeout(10):
            client = Client(
                token,
                session,
                conf_update_interval=timedelta(minutes=5),
                device_set_debounce=timedelta(milliseconds=500),
            )
            devices = await client.get_devices()
    except asyncio.TimeoutError:
        _LOGGER.debug("Connection timed out")
        raise ConfigEntryNotReady
    except ClientConnectionError:
        _LOGGER.debug("ClientConnectionError")
        raise ConfigEntryNotReady
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error when initializing client")
        return None

    return [MelCloudDevice(device) for device in devices]
