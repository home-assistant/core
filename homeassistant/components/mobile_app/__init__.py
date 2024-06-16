"""Integrates Native Apps to Home Assistant."""

from contextlib import suppress
from typing import Any

from homeassistant.components import cloud, notify as hass_notify
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

# Pre-import the platforms so they get loaded when the integration
# is imported as they are almost always going to be loaded and its
# cheaper to import them all at once.
from . import (  # noqa: F401
    binary_sensor as binary_sensor_pre_import,
    device_tracker as device_tracker_pre_import,
    notify as notify_pre_import,
    sensor as sensor_pre_import,
    websocket_api,
)
from .const import (
    ATTR_DEVICE_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OS_VERSION,
    CONF_CLOUDHOOK_URL,
    DATA_CONFIG_ENTRIES,
    DATA_DELETED_IDS,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .helpers import MobileApp, MobileAppConfigEntry, MobileAppData, savable_state
from .http_api import RegistrationsView
from .util import async_create_cloud_hook
from .webhook import handle_webhook

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the mobile app component."""
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    if (app_config := await store.async_load()) is None or not isinstance(
        app_config, dict
    ):
        app_config = {
            DATA_CONFIG_ENTRIES: {},
            DATA_DELETED_IDS: [],
        }

    hass.data[MobileApp] = MobileAppData(
        deleted_ids=app_config.get(DATA_DELETED_IDS, []), store=store
    )

    hass.http.register_view(RegistrationsView())

    for deleted_id in hass.data[MobileApp].deleted_ids:
        with suppress(ValueError):
            webhook_register(
                hass, DOMAIN, "Deleted Webhook", deleted_id, handle_webhook
            )

    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.NOTIFY, DOMAIN, {}, config),
        eager_start=True,
    )

    websocket_api.async_setup_commands(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a mobile_app entry."""
    registration = entry.data

    webhook_id = registration[CONF_WEBHOOK_ID]

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, registration[ATTR_DEVICE_ID])},
        manufacturer=registration[ATTR_MANUFACTURER],
        model=registration[ATTR_MODEL],
        name=registration[ATTR_DEVICE_NAME],
        sw_version=registration[ATTR_OS_VERSION],
    )

    hass.data.setdefault(MobileAppConfigEntry, {})[entry.entry_id] = MobileAppData(
        config_entries={webhook_id: entry}, devices={webhook_id: device}
    )

    registration_name = f"Mobile App: {registration[ATTR_DEVICE_NAME]}"
    webhook_register(hass, DOMAIN, registration_name, webhook_id, handle_webhook)

    async def manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if (
            state is cloud.CloudConnectionState.CLOUD_CONNECTED
            and CONF_CLOUDHOOK_URL not in entry.data
        ):
            await async_create_cloud_hook(hass, webhook_id, entry)

    if (
        CONF_CLOUDHOOK_URL not in entry.data
        and cloud.async_active_subscription(hass)
        and cloud.async_is_connected(hass)
    ):
        await async_create_cloud_hook(hass, webhook_id, entry)

    entry.async_on_unload(cloud.async_listen_connection_change(hass, manage_cloudhook))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await hass_notify.async_reload(hass, DOMAIN)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a mobile app entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    webhook_id = entry.data[CONF_WEBHOOK_ID]

    webhook_unregister(hass, webhook_id)

    data = hass.data[MobileApp]
    del data.config_entries[webhook_id]
    del data.devices[webhook_id]

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup when entry is removed."""
    data = hass.data[MobileApp]
    data.deleted_ids.append(entry.data[CONF_WEBHOOK_ID])
    if data.store:
        await data.store.async_save(savable_state(hass))

    if CONF_CLOUDHOOK_URL in entry.data:
        with suppress(cloud.CloudNotAvailable, ValueError):
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
