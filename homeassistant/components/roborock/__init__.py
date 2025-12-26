"""The Roborock component."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import timedelta
import logging
from typing import Any

from roborock import (
    RoborockException,
    RoborockInvalidCredentials,
    RoborockInvalidUserAgreement,
    RoborockNoUserAgreement,
)
from roborock.data import UserData
from roborock.devices.device import RoborockDevice
from roborock.devices.device_manager import UserParams, create_device_manager
from roborock.map.map_parser import MapParserConfig
from roborock.mqtt.session import MqttSessionUnauthorized

from homeassistant.const import CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_URL,
    CONF_SHOW_BACKGROUND,
    CONF_USER_DATA,
    DEFAULT_DRAWABLES,
    DOMAIN,
    DRAWABLES,
    MAP_SCALE,
    PLATFORMS,
)
from .coordinator import (
    RoborockB01Q7UpdateCoordinator,
    RoborockConfigEntry,
    RoborockCoordinators,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
    RoborockDataUpdateCoordinatorB01,
    RoborockWashingMachineUpdateCoordinator,
    RoborockWetDryVacUpdateCoordinator,
)
from .roborock_storage import CacheStore, async_cleanup_map_storage

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    await async_cleanup_map_storage(hass, entry.entry_id)

    user_data = UserData.from_dict(entry.data[CONF_USER_DATA])
    user_params = UserParams(
        username=entry.data[CONF_USERNAME],
        user_data=user_data,
        base_url=entry.data[CONF_BASE_URL],
    )
    cache = CacheStore(hass, entry.entry_id)
    try:
        device_manager = await create_device_manager(
            user_params,
            cache=cache,
            session=async_get_clientsession(hass),
            map_parser_config=MapParserConfig(
                drawables=[
                    drawable
                    for drawable, default_value in DEFAULT_DRAWABLES.items()
                    if entry.options.get(DRAWABLES, {}).get(drawable, default_value)
                ],
                show_background=entry.options.get(CONF_SHOW_BACKGROUND, False),
                map_scale=MAP_SCALE,
            ),
            mqtt_session_unauthorized_hook=lambda: entry.async_start_reauth(hass),
        )
    except RoborockInvalidCredentials as err:
        raise ConfigEntryAuthFailed(
            "Invalid credentials",
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except RoborockInvalidUserAgreement as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="invalid_user_agreement",
        ) from err
    except RoborockNoUserAgreement as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_user_agreement",
        ) from err
    except MqttSessionUnauthorized as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="mqtt_unauthorized",
        ) from err
    except RoborockException as err:
        _LOGGER.debug("Failed to get Roborock home data: %s", err)
        raise ConfigEntryNotReady(
            "Failed to get Roborock home data",
            translation_domain=DOMAIN,
            translation_key="home_data_fail",
        ) from err

    async def shutdown_roborock(_: Event | None = None) -> None:
        await asyncio.gather(device_manager.close(), cache.flush())

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_roborock)
    )
    entry.async_on_unload(shutdown_roborock)

    devices = await device_manager.get_devices()
    _LOGGER.debug("Device manager found %d devices", len(devices))

    coordinators = await asyncio.gather(
        *build_setup_functions(hass, entry, devices, user_data),
        return_exceptions=True,
    )
    v1_coords = [
        coord
        for coord in coordinators
        if isinstance(coord, RoborockDataUpdateCoordinator)
    ]
    a01_coords = [
        coord
        for coord in coordinators
        if isinstance(coord, RoborockDataUpdateCoordinatorA01)
    ]
    b01_coords = [
        coord
        for coord in coordinators
        if isinstance(coord, RoborockDataUpdateCoordinatorB01)
    ]
    if len(v1_coords) + len(a01_coords) + len(b01_coords) == 0:
        raise ConfigEntryNotReady(
            "No devices were able to successfully setup",
            translation_domain=DOMAIN,
            translation_key="no_coordinators",
        )
    entry.runtime_data = RoborockCoordinators(v1_coords, a01_coords, b01_coords)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _remove_stale_devices(hass, entry, devices)

    return True


def _remove_stale_devices(
    hass: HomeAssistant,
    entry: RoborockConfigEntry,
    devices: list[RoborockDevice],
) -> None:
    device_map: dict[str, RoborockDevice] = {device.duid: device for device in devices}
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=entry.entry_id
    )
    for device in device_entries:
        # Remove any devices that are no longer in the account.
        # The API returns all devices, even if they are offline
        device_duids = {
            identifier[1].replace("_dock", "") for identifier in device.identifiers
        }
        if any(device_duid in device_map for device_duid in device_duids):
            continue
        _LOGGER.info(
            "Removing device: %s because it is no longer exists in your account",
            device.name,
        )
        device_registry.async_update_device(
            device_id=device.id,
            remove_config_entry_id=entry.entry_id,
        )


async def async_migrate_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Migrate old configuration entries to the new format."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        entry.version,
        entry.minor_version,
    )
    if entry.version > 1:
        # Downgrade from future version
        return False

    # 1->2: Migrate from unique id as email address to unique id as rruid
    if entry.minor_version == 1:
        user_data = UserData.from_dict(entry.data[CONF_USER_DATA])
        _LOGGER.debug("Updating unique id to %s", user_data.rruid)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=user_data.rruid,
            version=1,
            minor_version=2,
        )

    return True


def build_setup_functions(
    hass: HomeAssistant,
    entry: RoborockConfigEntry,
    devices: list[RoborockDevice],
    user_data: UserData,
) -> list[
    Coroutine[
        Any,
        Any,
        RoborockDataUpdateCoordinator
        | RoborockDataUpdateCoordinatorA01
        | RoborockDataUpdateCoordinatorB01
        | None,
    ]
]:
    """Create a list of setup functions that can later be called asynchronously."""
    coordinators: list[
        RoborockDataUpdateCoordinator
        | RoborockDataUpdateCoordinatorA01
        | RoborockDataUpdateCoordinatorB01
    ] = []
    for device in devices:
        _LOGGER.debug("Creating device %s: %s", device.name, device)
        if device.v1_properties is not None:
            coordinators.append(
                RoborockDataUpdateCoordinator(hass, entry, device, device.v1_properties)
            )
        elif device.dyad is not None:
            coordinators.append(
                RoborockWetDryVacUpdateCoordinator(hass, entry, device, device.dyad)
            )
        elif device.zeo is not None:
            coordinators.append(
                RoborockWashingMachineUpdateCoordinator(hass, entry, device, device.zeo)
            )
        elif device.b01_q7_properties is not None:
            coordinators.append(
                RoborockB01Q7UpdateCoordinator(
                    hass, entry, device, device.b01_q7_properties
                )
            )
        else:
            _LOGGER.warning(
                "Not adding device %s because its protocol version %s or category %s is not supported",
                device.duid,
                device.device_info.pv,
                device.product.category.name,
            )

    return [setup_coordinator(coordinator) for coordinator in coordinators]


async def setup_coordinator(
    coordinator: RoborockDataUpdateCoordinator
    | RoborockDataUpdateCoordinatorA01
    | RoborockDataUpdateCoordinatorB01,
) -> (
    RoborockDataUpdateCoordinator
    | RoborockDataUpdateCoordinatorA01
    | RoborockDataUpdateCoordinatorB01
    | None
):
    """Set up a single coordinator."""
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise
    else:
        return coordinator


async def async_unload_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> None:
    """Handle removal of an entry."""
    store = CacheStore(hass, entry.entry_id)
    await store.async_remove()
