"""Platform for the Daikin AC."""
import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientConnectionError
from pydaikin.daikin_base import Appliance

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_UUID,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.util import Throttle

from .const import DOMAIN, KEY_MAC, TIMEOUT

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with Daikin."""
    conf = entry.data
    # For backwards compat, set unique ID
    if entry.unique_id is None or ".local" in entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=conf[KEY_MAC])

    daikin_api = await daikin_api_setup(
        hass,
        conf[CONF_HOST],
        conf.get(CONF_API_KEY),
        conf.get(CONF_UUID),
        conf.get(CONF_PASSWORD),
    )
    if not daikin_api:
        return False

    await async_migrate_unique_id(hass, entry, daikin_api)

    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: daikin_api})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def daikin_api_setup(hass: HomeAssistant, host, key, uuid, password):
    """Create a Daikin instance only once."""

    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(TIMEOUT):
            device = await Appliance.factory(
                host, session, key=key, uuid=uuid, password=password
            )
    except asyncio.TimeoutError as err:
        _LOGGER.debug("Connection to %s timed out", host)
        raise ConfigEntryNotReady from err
    except ClientConnectionError as err:
        _LOGGER.debug("ClientConnectionError to %s", host)
        raise ConfigEntryNotReady from err
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error creating device %s", host)
        return None

    api = DaikinApi(device)

    return api


class DaikinApi:
    """Keep the Daikin instance in one place and centralize the update."""

    def __init__(self, device: Appliance) -> None:
        """Initialize the Daikin Handle."""
        self.device = device
        self.name = device.values.get("name", "Daikin AC")
        self.ip_address = device.device_ip
        self._available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Pull the latest data from Daikin."""
        try:
            await self.device.update_status()
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.ip_address)
            self._available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        info = self.device.values
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            manufacturer="Daikin",
            model=info.get("model"),
            name=info.get("name"),
            sw_version=info.get("ver", "").replace("_", "."),
        )


async def async_migrate_unique_id(
    hass: HomeAssistant, config_entry: ConfigEntry, api: DaikinApi
) -> None:
    """Migrate old entry."""
    dev_reg = dr.async_get(hass)
    old_unique_id = config_entry.unique_id
    new_unique_id = api.device.mac
    new_name = api.device.values.get("name")

    @callback
    def _update_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        return update_unique_id(entity_entry, new_unique_id)

    if new_unique_id == old_unique_id:
        return

    # Migrate devices
    for device_entry in dr.async_entries_for_config_entry(
        dev_reg, config_entry.entry_id
    ):
        for connection in device_entry.connections:
            if connection[1] == old_unique_id:
                new_connections = {
                    (CONNECTION_NETWORK_MAC, dr.format_mac(new_unique_id))
                }

                _LOGGER.debug(
                    "Migrating device %s connections to %s",
                    device_entry.name,
                    new_connections,
                )
                dev_reg.async_update_device(
                    device_entry.id,
                    merge_connections=new_connections,
                )

        if device_entry.name is None:
            _LOGGER.debug(
                "Migrating device name to %s",
                new_name,
            )
            dev_reg.async_update_device(
                device_entry.id,
                name=new_name,
            )

        # Migrate entities
        await er.async_migrate_entries(hass, config_entry.entry_id, _update_unique_id)

        new_data = {**config_entry.data, KEY_MAC: dr.format_mac(new_unique_id)}

        hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, data=new_data
        )


@callback
def update_unique_id(
    entity_entry: er.RegistryEntry, unique_id: str
) -> dict[str, str] | None:
    """Update unique ID of entity entry."""
    if entity_entry.unique_id.startswith(unique_id):
        # Already correct, nothing to do
        return None

    unique_id_parts = entity_entry.unique_id.split("-")
    unique_id_parts[0] = unique_id
    entity_new_unique_id = "-".join(unique_id_parts)

    _LOGGER.debug(
        "Migrating entity %s from %s to new id %s",
        entity_entry.entity_id,
        entity_entry.unique_id,
        entity_new_unique_id,
    )
    return {"new_unique_id": entity_new_unique_id}
