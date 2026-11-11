"""Mobile app utility functions."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import asyncio
from collections.abc import Mapping
from contextlib import suppress
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import cloud, person
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    OperationNotAllowed,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    ATTR_APP_DATA,
    ATTR_DEVICE_NAME,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_PUSH_WEBSOCKET_CHANNEL,
    CONF_CLOUDHOOK_URL,
    CONF_USER_ID,
    DATA_CONFIG_ENTRIES,
    DATA_DELETED_IDS,
    DATA_DEVICES,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_NOTIFY,
    DATA_PENDING_UPDATES,
    DATA_STORE,
    DOMAIN,
)
from .helpers import savable_state

if TYPE_CHECKING:
    from .notify import MobileAppNotificationService

_LOGGER = logging.getLogger(__name__)


@callback
def webhook_id_from_device_id(hass: HomeAssistant, device_id: str) -> str | None:
    """Get webhook ID from device ID."""
    if DOMAIN not in hass.data:
        return None

    for cur_webhook_id, cur_device in hass.data[DOMAIN][DATA_DEVICES].items():
        if cur_device.id == device_id:
            return cur_webhook_id

    return None


@callback
def supports_push(hass: HomeAssistant, webhook_id: str) -> bool:
    """Return if push notifications is supported."""
    config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]
    app_data = config_entry.data[ATTR_APP_DATA]
    return (
        ATTR_PUSH_TOKEN in app_data and ATTR_PUSH_URL in app_data
    ) or ATTR_PUSH_WEBSOCKET_CHANNEL in app_data


@callback
def get_notify_service(hass: HomeAssistant, webhook_id: str) -> str | None:
    """Return the notify service for this webhook ID."""
    notify_service: MobileAppNotificationService = hass.data[DOMAIN][DATA_NOTIFY]

    for target_service, target_webhook_id in notify_service.registered_targets.items():
        if target_webhook_id == webhook_id:
            return target_service

    return None


_CLOUD_HOOK_LOCK = asyncio.Lock()


async def async_create_cloud_hook(
    hass: HomeAssistant, webhook_id: str, entry: ConfigEntry | None
) -> str:
    """Create a cloud hook."""
    async with _CLOUD_HOOK_LOCK:
        hook = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
        if entry is None:
            return hook
        if entry.data[CONF_WEBHOOK_ID] != webhook_id:
            # The app registered again with another webhook while awaiting
            with suppress(cloud.CloudNotAvailable, ValueError):
                await cloud.async_delete_cloudhook(hass, webhook_id)
            return hook
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CLOUDHOOK_URL: hook}
        )
        return hook


async def async_retire_webhook(
    hass: HomeAssistant, registration: Mapping[str, Any]
) -> None:
    """Retire the webhook of a registration and delete its cloudhook."""
    webhook_id = registration[CONF_WEBHOOK_ID]
    hass.data[DOMAIN][DATA_DELETED_IDS].append(webhook_id)
    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS].pop(webhook_id, None)
    store = hass.data[DOMAIN][DATA_STORE]
    await store.async_save(savable_state(hass))
    await async_delete_registration_cloudhook(hass, registration)


async def async_delete_registration_cloudhook(
    hass: HomeAssistant, registration: Mapping[str, Any]
) -> None:
    """Delete the cloudhook of a registration, if it has one."""
    if CONF_CLOUDHOOK_URL in registration:
        with suppress(cloud.CloudNotAvailable, ValueError):
            await cloud.async_delete_cloudhook(hass, registration[CONF_WEBHOOK_ID])


@callback
def _async_move_sensors(
    hass: HomeAssistant, entry: ConfigEntry, from_webhook_id: str, to_webhook_id: str
) -> None:
    """Move the sensors of an entry to another webhook ID."""
    entity_registry = er.async_get(hass)
    # Sensor unique IDs are prefixed with the webhook ID
    from_prefix = f"{from_webhook_id}_"
    to_prefix = f"{to_webhook_id}_"
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id.startswith(from_prefix):
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=to_prefix + entity.unique_id.removeprefix(from_prefix),
            )

    # Updates of disabled sensors are kept until the sensor is enabled
    for pending_updates in hass.data[DOMAIN][DATA_PENDING_UPDATES].values():
        for unique_id in [
            uid for uid in pending_updates if uid.startswith(from_prefix)
        ]:
            update = pending_updates.pop(unique_id)
            update[CONF_WEBHOOK_ID] = to_webhook_id
            pending_updates[to_prefix + unique_id.removeprefix(from_prefix)] = update


async def async_update_registration(
    hass: HomeAssistant, entry: ConfigEntry, registration: dict[str, Any]
) -> bool:
    """Update the entry of an app which registers again.

    Must be called with the registration lock held. Return True if the entry
    has been reloaded with the new registration, otherwise the entry keeps the
    old registration and the cloudhook of the new one is deleted.
    """
    if entry.state is ConfigEntryState.FAILED_UNLOAD:
        # The entry can't be reloaded, so changing it couldn't be undone
        await async_delete_registration_cloudhook(hass, registration)
        return False

    old_registration = entry.data
    old_title = entry.title
    old_disabled_by = entry.disabled_by
    old_webhook_id = old_registration[CONF_WEBHOOK_ID]
    new_webhook_id = registration[CONF_WEBHOOK_ID]

    _async_move_sensors(hass, entry, old_webhook_id, new_webhook_id)
    hass.config_entries.async_update_entry(
        entry, title=registration[ATTR_DEVICE_NAME], data=registration
    )
    try:
        if old_disabled_by:
            # The apps register again when the webhook of a disabled entry
            # doesn't respond, so enable the entry instead of failing each time
            reloaded = await hass.config_entries.async_set_disabled_by(
                entry.entry_id, None
            )
        else:
            reloaded = await hass.config_entries.async_reload(entry.entry_id)
    except OperationNotAllowed:
        reloaded = False

    # The reload doesn't set up the entry if it was disabled meanwhile
    if not reloaded or entry.state is not ConfigEntryState.LOADED:
        # The app keeps using the old registration when registering fails
        _async_move_sensors(hass, entry, new_webhook_id, old_webhook_id)
        hass.config_entries.async_update_entry(
            entry, title=old_title, data=old_registration
        )
        # Fails if the entry is in a state which can't be unloaded
        with suppress(OperationNotAllowed):
            if old_disabled_by:
                await hass.config_entries.async_set_disabled_by(
                    entry.entry_id, old_disabled_by
                )
            elif not entry.disabled_by and entry.state.recoverable:
                # Set up the entry again with the old registration
                await hass.config_entries.async_reload(entry.entry_id)
        await async_delete_registration_cloudhook(hass, registration)
        return False

    # The app uses the new registration, so it must not fail on cleanup errors
    try:
        await async_retire_webhook(hass, old_registration)
    except Exception:
        _LOGGER.exception("Error retiring the old webhook of %s", entry.title)

    entity_registry = er.async_get(hass)
    if devt_entity_id := entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, registration[ATTR_DEVICE_ID]
    ):
        await person.async_add_user_device_tracker(
            hass, registration[CONF_USER_ID], devt_entity_id
        )
    return True
