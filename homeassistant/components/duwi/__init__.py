"""Support for Duwi Smart devices."""

import asyncio
import functools
import time
from typing import Any, NamedTuple

from duwi_smarthome_sdk.base_api import CustomerApi, SharingTokenListener
from duwi_smarthome_sdk.device_scene_models import CustomerDevice, CustomerScene
from duwi_smarthome_sdk.manager import Manager, SharingDeviceListener
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    _LOGGER,
    ACCESS_TOKEN,
    ADDRESS,
    APP_KEY,
    APP_SECRET,
    CLIENT_MODEL,
    CLIENT_VERSION,
    DOMAIN,
    DUWI_DISCOVERY_NEW,
    DUWI_HA_SIGNAL_UPDATE_ENTITY,
    DUWI_SCENE_UPDATE,
    HOUSE_KEY,
    HOUSE_NAME,
    HOUSE_NO,
    PASSWORD,
    PHONE,
    REFRESH_TOKEN,
    SUPPORTED_PLATFORMS,
    WS_ADDRESS,
)

type DuwiConfigEntry = ConfigEntry[HomeAssistantDuwiData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(domain=DOMAIN)


class HomeAssistantDuwiData(NamedTuple):
    """Duwi data stored in the Home Assistant data object."""

    manager: Manager
    listener: SharingDeviceListener


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Duwi Smart Devices integration."""

    # Check for existing config entries for this integration
    hass.data.setdefault(DOMAIN, {})
    if not hass.config_entries.async_entries(DOMAIN):
        # No entries found, initiate the configuration flow
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

    # Setup was successful
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DuwiConfigEntry) -> bool:
    """Set up a config entry for the Duwi Smart Devices integration."""

    hass.data.setdefault(DOMAIN, {})

    token_listener = TokenListener(hass, entry)
    manager: Manager = Manager(
        _id=entry.entry_id,
        customer_api=CustomerApi(
            address=entry.data[ADDRESS],
            ws_address=entry.data[WS_ADDRESS],
            app_key=entry.data[APP_KEY],
            app_secret=entry.data[APP_SECRET],
            house_no=entry.data[HOUSE_NO],
            house_name=entry.data[HOUSE_NAME],
            access_token=entry.data[ACCESS_TOKEN],
            refresh_token=entry.data[REFRESH_TOKEN],
            client_version=CLIENT_VERSION,
            client_model=CLIENT_MODEL,
            app_version=__version__,
        ),
        house_key=entry.data.get(HOUSE_KEY),
        token_listener=token_listener,
    )

    login_status = await manager.init_manager(
        entry.data["phone"], entry.data["password"]
    )

    if not login_status:
        raise ConfigEntryAuthFailed(
            "User authentication failed, please try reloading the integration or adding again."
        )

    # Fetch devices
    is_online = await manager.update_device_cache()
    listener = DeviceListener(hass, manager)
    manager.add_device_listener(listener)

    ids = []
    if hass.data[DOMAIN].get(entry.entry_id) is not None:
        old_manager = hass.data[DOMAIN].get(entry.entry_id, {}).manager
        ids = await compare_manager(old_manager, manager, None)

    hass.data[DOMAIN][entry.entry_id] = HomeAssistantDuwiData(
        manager=manager, listener=listener
    )

    # Clean up inappropriate devices
    await cleanup_device_registry(hass, ids)
    hass.data[DOMAIN].setdefault("existing_house", []).append(entry.data[HOUSE_NO])

    # Start global WebSocket listener
    if is_online:
        await hass.async_create_task(manager.ws.reconnect())
    else:
        hass.loop.create_task(manager.ws.reconnect())

    hass.loop.create_task(manager.ws.listen())
    hass.loop.create_task(manager.ws.keep_alive())

    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True


async def compare_manager(
    old_manager: Manager | None, new_manager: Manager, devices: list | None
) -> list:
    """Compare old and new manager to find devices with different room or type."""

    ids = []

    if not old_manager:
        # If there is no old manager, check for differences in the new manager
        if devices is not None and new_manager.device_map is not None:
            for d in devices:
                d2 = new_manager.device_map.get(d.device_no)
                if not d2:
                    # Device not found in new manager
                    continue

                # Compare room and device type; if different, add device ID to the list
                if (
                    d.room_no != d2.room_no
                    or d.device_sub_type_no != d2.device_sub_type_no
                ):
                    ids.append(d.device_no)
        return ids

    # Compare devices in both managers
    for dev_id in old_manager.device_map:
        d1 = old_manager.device_map.get(dev_id)
        d2 = new_manager.device_map.get(dev_id)
        if not d2:
            # Device not found in new manager
            continue

        # Compare room and device type; if different, add device ID to the list
        if d1.room_no != d2.room_no or d1.device_sub_type_no != d2.device_sub_type_no:
            ids.append(dev_id)

    return ids


async def cleanup_device_registry(hass: HomeAssistant, device_ids: list) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""

    device_registry = dr.async_get(hass)

    for dev_id, device_entry in list(device_registry.devices.items()):
        if should_remove_device(hass, device_entry.identifiers, device_ids):
            device_registry.async_remove_device(dev_id)


def should_remove_device(hass, identifiers, device_ids):
    """Determine if a device should be removed based on its identifiers."""

    for item in identifiers:
        if item[0] == DOMAIN:
            # Prepare to remove Duwi device
            read_to_remove = True

            for v in hass.data[DOMAIN].values():
                if hasattr(v, "manager") and item[1] in v.manager.device_map:
                    read_to_remove = False
                    break

            return read_to_remove or item[1] in device_ids
    return False


async def async_unload_entry(hass: HomeAssistant, entry: DuwiConfigEntry) -> bool:
    """Unload the Duwi platforms associated with the provided config entry."""

    # Attempt to unload all platforms associated with the entry.
    await hass.data[DOMAIN][entry.entry_id].manager.unload()

    house_no = entry.data.get(HOUSE_NO)
    if house_no in hass.data[DOMAIN].get("existing_house"):
        hass.data[DOMAIN]["existing_house"].remove(house_no)

    if lp := hass.data[DOMAIN].get("lp"):
        _LOGGER.info("Clearing hosts from async_unload_entry")
        lp.clear_hosts(entry.entry_id)

    return await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: DuwiConfigEntry) -> None:
    """Remove a config entry and revoke credentials from Duwi."""

    manager = hass.data[DOMAIN][entry.entry_id].manager

    # Cleanup device registry for the devices managed by this entry
    await cleanup_device_registry(hass, manager.device_map.keys())

    # Unload the manager and remove entry data
    await manager.unload(True)
    hass.data[DOMAIN].pop(entry.entry_id)

    house_no_list: list = hass.data[DOMAIN].get("existing_house", [])

    if lp := hass.data[DOMAIN].get("lp"):
        _LOGGER.info("Clearing hosts from async_remove_entry")
        lp.clear_hosts(entry.entry_id)

        if not house_no_list:
            # Last entry removed; stopping the lp service
            _LOGGER.info("Last entry removed from async_remove_entry")
            lp.stop()
            hass.data[DOMAIN].pop("lp")

    await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS)


class DeviceListener(SharingDeviceListener):
    """Device Update Listener."""

    def __init__(self, hass: HomeAssistant, manager: Manager) -> None:
        """Initialize the DeviceListener."""
        self.hass = hass
        self.manager = manager

    def update_scene(self, scene: CustomerScene) -> None:
        """Notify about scene update."""
        dispatcher_send(self.hass, f"{DUWI_SCENE_UPDATE}_{scene.scene_no}")

    def update_device(self, device: CustomerDevice) -> None:
        """Update device status notification."""
        dispatcher_send(self.hass, f"{DUWI_HA_SIGNAL_UPDATE_ENTITY}_{device.device_no}")

    def add_device(self, device: CustomerDevice) -> None:
        """Handle a new device being added."""
        # Ensure the device isn't present stale
        self.async_remove_device(device.device_no)
        dispatcher_send(self.hass, DUWI_DISCOVERY_NEW, [device.device_no])

    def remove_device(self, device_no: str) -> None:
        """Schedule removal of a device."""
        self.hass.add_job(self.async_remove_device, device_no)

    def token_listener(self, token_info: dict[str, Any]) -> None:
        """Handle token update notifications."""
        # Implementation needed (if applicable)

    @callback
    def async_remove_device(self, device_no: str) -> None:
        """Remove device from Home Assistant."""
        device_registry = dr.async_get(self.hass)
        _LOGGER.info("Removing device_no %s", device_no)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_no)}
        )

        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)


class TokenListener(SharingTokenListener):
    """Token listener for upstream token updates."""

    def __init__(self, hass: HomeAssistant, entry: DuwiConfigEntry) -> None:
        """Initialize the TokenListener."""
        self.hass = hass
        self.entry = entry

    def update_token(
        self, is_refresh: bool, token_info: dict[str, Any] | None = None
    ) -> None:
        """Update token info in the config entry."""
        _LOGGER.info("Updating token: %s %s", is_refresh, token_info)

        if is_refresh:
            # Prepare data for updating the config entry
            data = {
                PHONE: self.entry.data[PHONE] if self.entry.data is not None else None,
                PASSWORD: self.entry.data[PASSWORD]
                if self.entry.data is not None
                else None,
                HOUSE_KEY: self.entry.data[HOUSE_KEY]
                if self.entry.data is not None
                else None,
                ADDRESS: self.entry.data[ADDRESS]
                if self.entry.data is not None
                else None,
                WS_ADDRESS: self.entry.data[WS_ADDRESS]
                if self.entry.data is not None
                else None,
                APP_KEY: self.entry.data[APP_KEY]
                if self.entry.data is not None
                else None,
                APP_SECRET: self.entry.data[APP_SECRET]
                if self.entry.data is not None
                else None,
                HOUSE_NO: self.entry.data[HOUSE_NO]
                if self.entry.data is not None
                else None,
                ACCESS_TOKEN: token_info[ACCESS_TOKEN]
                if token_info is not None
                else None,
                REFRESH_TOKEN: token_info[REFRESH_TOKEN]
                if token_info is not None
                else None,
            }
        else:
            raise ConfigEntryAuthFailed(
                "Failed to refresh token, please try reloading the integration or re-adding it."
            )

        @callback
        def async_update_entry() -> None:
            """Update the configuration entry with new token data."""
            self.hass.config_entries.async_update_entry(self.entry, data=data)

        # Schedule the asynchronous update job
        self.hass.add_job(async_update_entry)


def debounce(wait: float):
    """Debounce a function, ensuring it is called after a specified wait time."""

    def decorator(fn):
        last_call = 0  # Timestamp of the last call
        call_pending = None  # Task for the pending call

        @functools.wraps(fn)
        async def debounced(*args, **kwargs):
            nonlocal last_call, call_pending

            now = time.time()  # Get current time
            if now - last_call < wait:
                # If the function was called recently
                if call_pending:
                    # Cancel the previous pending call if it exists
                    call_pending.cancel()
                # Create a new task that waits for the remaining time
                call_pending = asyncio.create_task(
                    asyncio.sleep(wait - (now - last_call))
                )
                await call_pending

            last_call = time.time()  # Update last call timestamp
            return await fn(*args, **kwargs)  # Call the actual function

        return debounced

    return decorator
