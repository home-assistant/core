"""Support for Duwi Smart devices."""

from typing import Any, NamedTuple

from duwi_smarthome_sdk.base_api import CustomerApi
from duwi_smarthome_sdk.device_scene_models import CustomerDevice, CustomerScene
from duwi_smarthome_sdk.manager import Manager, SharingDeviceListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

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


class HomeAssistantDuwiData(NamedTuple):
    """Store Duwi data in the Home Assistant data object."""

    manager: Manager
    listener: SharingDeviceListener


async def async_setup_entry(hass: HomeAssistant, entry: DuwiConfigEntry) -> bool:
    """Set up a config entry for the Duwi Smart Devices integration."""

    hass.data.setdefault(DOMAIN, {})

    manager: Manager = Manager(
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
        token_refresh_callback=update_token,
    )

    # Fetch devices
    await manager.init_manager()
    await manager.update_device_cache()
    listener = DeviceListener(hass, manager)
    manager.add_device_listener(listener)

    entry.runtime_data = HomeAssistantDuwiData(manager=manager, listener=listener)

    # Clean up inappropriate devices
    await cleanup_device_registry(hass, entry)

    # Start global WebSocket listener
    await hass.async_create_task(manager.ws.reconnect())

    hass.loop.create_task(manager.ws.listen())
    hass.loop.create_task(manager.ws.keep_alive())

    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True


async def compare_manager(old_manager: Manager, new_manager: Manager) -> list:
    """Compare old and new manager to find devices with different room or type."""

    ids = []

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


async def cleanup_device_registry(hass: HomeAssistant, entry: DuwiConfigEntry) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""

    device_registry = dr.async_get(hass)

    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and (
                item[1] not in entry.runtime_data.manager.device_map
            ):
                device_registry.async_remove_device(dev_id)


async def async_unload_entry(hass: HomeAssistant, entry: DuwiConfigEntry) -> bool:
    """Unload the Duwi platforms associated with the provided config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, SUPPORTED_PLATFORMS
    ):
        await entry.runtime_data.manager.unload(True)

    return unload_ok


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


@callback
def update_token(
    self, is_refresh: bool, token_info: dict[str, Any] | None = None
) -> None:
    """Update token info in the config entry."""
    _LOGGER.info("Updating token: %s %s", is_refresh, token_info)

    if is_refresh:
        # Prepare data for updating the config entry
        data = {
            PHONE: self.entry.data[PHONE] if self.entry.data is not None else None,
            PASSWORD: (
                self.entry.data[PASSWORD] if self.entry.data is not None else None
            ),
            HOUSE_KEY: (
                self.entry.data[HOUSE_KEY] if self.entry.data is not None else None
            ),
            ADDRESS: (
                self.entry.data[ADDRESS] if self.entry.data is not None else None
            ),
            WS_ADDRESS: (
                self.entry.data[WS_ADDRESS] if self.entry.data is not None else None
            ),
            APP_KEY: (
                self.entry.data[APP_KEY] if self.entry.data is not None else None
            ),
            APP_SECRET: (
                self.entry.data[APP_SECRET] if self.entry.data is not None else None
            ),
            HOUSE_NO: (
                self.entry.data[HOUSE_NO] if self.entry.data is not None else None
            ),
            ACCESS_TOKEN: (
                token_info[ACCESS_TOKEN] if token_info is not None else None
            ),
            REFRESH_TOKEN: (
                token_info[REFRESH_TOKEN] if token_info is not None else None
            ),
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
