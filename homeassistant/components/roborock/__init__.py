"""The Roborock component."""

import asyncio
from datetime import timedelta
import logging

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
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BASE_URL,
    CONF_SHOW_BACKGROUND,
    CONF_SHOW_ROOMS,
    CONF_SHOW_WALLS,
    CONF_USER_DATA,
    DEFAULT_DRAWABLES,
    DOMAIN,
    DRAWABLES,
    MAP_SCALE,
    PLATFORMS,
)
from .coordinator import (
    RoborockB01Q7UpdateCoordinator,
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockCoordinators,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
    RoborockDataUpdateCoordinatorB01,
    RoborockWashingMachineUpdateCoordinator,
    RoborockWetDryVacUpdateCoordinator,
)
from .models import get_device_info
from .roborock_storage import CacheStore, async_cleanup_map_storage
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


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

    entry.runtime_data = RoborockCoordinators()

    @callback
    def handle_device_ready(device: RoborockDevice) -> None:
        """Handle a device becoming ready."""
        entry.async_create_background_task(
            hass,
            async_setup_device(hass, entry, device),
            name=f"roborock_device_setup_{device.duid}",
        )

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
                show_rooms=entry.options.get(CONF_SHOW_ROOMS, True),
                show_walls=entry.options.get(CONF_SHOW_WALLS, True),
                map_scale=MAP_SCALE,
            ),
            ready_callback=handle_device_ready,
            mqtt_session_unauthorized_hook=lambda: entry.async_start_reauth(hass),
            prefer_cache=False,
        )
    except RoborockInvalidCredentials as err:
        raise ConfigEntryAuthFailed(
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _remove_stale_devices(hass, entry, devices)

    return True


def _is_device_disabled(
    device_registry: dr.DeviceRegistry,
    device: RoborockDevice,
) -> bool:
    """Check if a device is disabled in the device registry."""
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, device.duid)})
    return device_entry is not None and device_entry.disabled


def _remove_stale_devices(
    hass: HomeAssistant,
    entry: RoborockConfigEntry,
    devices: list[RoborockDevice],
) -> None:
    """Remove devices from the registry that are no longer in the account."""
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
            "Removing device: %s because it no longer exists in your account",
            device.name,
        )
        device_registry.async_remove_device(device.id)


async def async_migrate_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Migrate old configuration entries to the new format."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        entry.version,
        entry.minor_version,
    )

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


async def async_setup_device(
    hass: HomeAssistant,
    entry: RoborockConfigEntry,
    device: RoborockDevice,
) -> None:
    """Set up a single Roborock device and its coordinator."""
    _LOGGER.debug("Device %s is ready, setting it up", device.duid)
    if device.duid in entry.runtime_data:
        return
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **get_device_info(device),
    )
    if _is_device_disabled(device_registry, device):
        _LOGGER.debug("Device %s is disabled, skipping setup", device.duid)
        try:
            await device.close()
        except RoborockException as err:
            _LOGGER.warning("Failed to close device %s: %s", device.duid, err)
        return

    _LOGGER.debug("Creating device %s: %s", device.name, device)
    coordinator: (
        RoborockDataUpdateCoordinator
        | RoborockDataUpdateCoordinatorA01
        | RoborockDataUpdateCoordinatorB01
        | RoborockB01Q10UpdateCoordinator
        | None
    ) = None
    if device.v1_properties is not None:
        coordinator = RoborockDataUpdateCoordinator(
            hass, entry, device, device.v1_properties
        )
    elif device.dyad is not None:
        coordinator = RoborockWetDryVacUpdateCoordinator(
            hass, entry, device, device.dyad
        )
    elif device.zeo is not None:
        coordinator = RoborockWashingMachineUpdateCoordinator(
            hass, entry, device, device.zeo
        )
    elif device.b01_q7_properties is not None:
        coordinator = RoborockB01Q7UpdateCoordinator(
            hass, entry, device, device.b01_q7_properties
        )
    elif device.b01_q10_properties is not None:
        coordinator = RoborockB01Q10UpdateCoordinator(
            hass, entry, device, device.b01_q10_properties
        )
    else:
        _LOGGER.warning(
            "Not adding entities for device %s (%s/%s) because its protocol"
            " version %s or category %s is not supported",
            device.duid,
            device.product.name,
            device.product.model,
            device.device_info.pv,
            device.product.category.name,
        )
        try:
            await device.close()
        except RoborockException as err:
            _LOGGER.warning("Failed to close device %s: %s", device.duid, err)
        return

    try:
        await coordinator.async_refresh()
    except RoborockException as err:
        _LOGGER.error(
            "Failed initial attempt to connect to device %s (%s): %s",
            device.name,
            device.duid,
            err,
        )

    entry.runtime_data.add(coordinator)
    async_dispatcher_send(
        hass,
        f"roborock_coordinator_added_{entry.entry_id}",
        coordinator,
    )


async def async_unload_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> None:
    """Handle removal of an entry."""
    store = CacheStore(hass, entry.entry_id)
    await store.async_remove()
