"""The myUplink integration."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import ClientError, ClientResponseError
from myuplink import MyUplinkAPI, get_manufacturer, get_model, get_system_name

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
)

from .api import AsyncConfigEntryAuth
from .const import DOMAIN, OAUTH2_SCOPES
from .coordinator import MyUplinkDataCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up myUplink from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, implementation)
    auth = AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)

    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if err.status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    if set(config_entry.data["token"]["scope"].split(" ")) != set(OAUTH2_SCOPES):
        raise ConfigEntryAuthFailed("Incorrect OAuth2 scope")

    # Setup MyUplinkAPI and coordinator for data fetch
    api = MyUplinkAPI(auth)
    coordinator = MyUplinkDataCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Update device registry
    create_devices(hass, config_entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def create_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator: MyUplinkDataCoordinator
) -> None:
    """Update all devices."""
    device_registry = dr.async_get(hass)

    for system in coordinator.data.systems:
        devices_in_system = [x.id for x in system.devices]
        for device_id, device in coordinator.data.devices.items():
            if device_id in devices_in_system:
                device_registry.async_get_or_create(
                    config_entry_id=config_entry.entry_id,
                    identifiers={(DOMAIN, device_id)},
                    name=get_system_name(system),
                    manufacturer=get_manufacturer(device),
                    model=get_model(device),
                    sw_version=device.firmwareCurrent,
                    serial_number=device.product_serial_number,
                )
