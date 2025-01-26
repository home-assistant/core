"""The SwitchBee Smart Home integration."""

from __future__ import annotations

import logging
import re

from aiohttp import ClientSession
from switchbee.api import CentralUnitPolling, CentralUnitWsRPC, is_wsrpc_api
from switchbee.api.central_unit import SwitchBeeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SWITCH,
]


async def get_api_object(
    central_unit: str, user: str, password: str, websession: ClientSession
) -> CentralUnitPolling | CentralUnitWsRPC:
    """Return SwitchBee API object."""

    api: CentralUnitPolling | CentralUnitWsRPC = CentralUnitPolling(
        central_unit, user, password, websession
    )
    # First try to connect and fetch the version
    try:
        await api.connect()
    except SwitchBeeError as exp:
        raise ConfigEntryNotReady("Failed to connect to the Central Unit") from exp

    # Check if websocket version
    if is_wsrpc_api(api):
        api = CentralUnitWsRPC(central_unit, user, password, websession)
        await api.connect()

    return api


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBee Smart Home from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    central_unit = entry.data[CONF_HOST]
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = await get_api_object(central_unit, user, password, websession)

    coordinator = SwitchBeeCoordinator(
        hass,
        api,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        dev_reg = dr.async_get(hass)
        websession = async_get_clientsession(hass, verify_ssl=False)
        old_unique_id = config_entry.unique_id
        assert isinstance(old_unique_id, str)
        api = await get_api_object(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            websession,
        )
        new_unique_id = api.unique_id

        @callback
        def update_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            """Update unique ID of entity entry."""
            if match := re.match(
                rf"(?:{old_unique_id})-(?P<id>\d+)", entity_entry.unique_id
            ):
                entity_new_unique_id = f"{new_unique_id}-{match.group('id')}"
                _LOGGER.debug(
                    "Migrating entity %s from %s to new id %s",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                    entity_new_unique_id,
                )
                return {"new_unique_id": entity_new_unique_id}

            return None

        if new_unique_id:
            # Migrate devices
            for device_entry in dr.async_entries_for_config_entry(
                dev_reg, config_entry.entry_id
            ):
                assert isinstance(device_entry, dr.DeviceEntry)
                for identifier in device_entry.identifiers:
                    if match := re.match(
                        rf"(?P<id>.+)-{old_unique_id}$", identifier[1]
                    ):
                        new_identifiers = {
                            (
                                DOMAIN,
                                f"{match.group('id')}-{new_unique_id}",
                            )
                        }
                        _LOGGER.debug(
                            "Migrating device %s identifiers from %s to %s",
                            device_entry.name,
                            device_entry.identifiers,
                            new_identifiers,
                        )
                        dev_reg.async_update_device(
                            device_entry.id, new_identifiers=new_identifiers
                        )

            # Migrate entities
            await er.async_migrate_entries(
                hass, config_entry.entry_id, update_unique_id
            )

            hass.config_entries.async_update_entry(config_entry, version=2)

        _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
