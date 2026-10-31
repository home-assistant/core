"""The Netatmo integration."""

import logging

from homeassistant.components import cloud
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import DOMAIN, PLATFORMS
from .coordinator import NetatmoConfigEntry, NetatmoDataHandler
from .services import async_setup_services
from .webhook import NetatmoWebhookManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Netatmo component."""
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NetatmoConfigEntry) -> None:
    """Set up Netatmo from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    # Set unique id if non was set (migration)
    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    session = OAuth2Session(hass, entry, implementation)
    await session.async_ensure_token_valid()

    required_scopes = set(api.get_api_scopes(entry.data["auth_implementation"]))
    raw_token_scopes = session.token["scope"]
    token_scopes = (
        set(raw_token_scopes.split())
        if isinstance(raw_token_scopes, str)
        else set(raw_token_scopes)
    )
    if not (token_scopes & required_scopes):
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="missing_scopes",
            translation_placeholders={
                "scopes": ", ".join(sorted(required_scopes - token_scopes))
            },
        )

    # Some, but not all, required scopes are granted: the token still works,
    # so let setup succeed and only prompt for reauth to fill the gap.
    # async_start_reauth is a no-op while a reauth/reconfigure flow is
    # already in progress for this entry, so this does not spam duplicate
    # flows across reloads within one run. It intentionally does not persist
    # a "already prompted" marker either: a config flow does not survive a
    # restart, and neither should our record of having started one, or a
    # dismissed prompt would silently never come back.
    if missing_scopes := required_scopes - token_scopes:
        _LOGGER.warning(
            "Session is missing scopes: %s; requesting reauthentication to grant them",
            sorted(missing_scopes),
        )
        entry.async_start_reauth(hass)

    auth = api.AsyncConfigEntryNetatmoAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    data_handler = NetatmoDataHandler(hass, entry, auth)
    entry.runtime_data = data_handler
    await data_handler.async_setup()

    webhook_manager = NetatmoWebhookManager(hass, entry)
    data_handler.webhook_manager = webhook_manager
    entry.async_on_unload(webhook_manager.cancel_pending_attempt)

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            await webhook_manager.async_ensure_registered()
        entry.async_on_unload(
            cloud.async_listen_connection_change(
                hass, webhook_manager.async_handle_cloud_state
            )
        )
    else:
        entry.async_on_unload(
            async_at_started(hass, webhook_manager.async_ensure_registered)
        )

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, webhook_manager.async_unregister
        )
    )

    entry.async_on_unload(entry.add_update_listener(async_config_entry_updated))


async def async_config_entry_updated(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}")


async def async_unload_entry(hass: HomeAssistant, entry: NetatmoConfigEntry) -> None:
    """Unload a config entry."""
    # Through the manager, so the drop cannot overtake a registration in flight.
    # A setup that never got as far as the data handler has nothing to drop.
    if (data_handler := getattr(entry, "runtime_data", None)) is not None:
        await data_handler.webhook_manager.async_unregister()

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: NetatmoConfigEntry) -> None:
    """Cleanup when entry is removed."""
    if CONF_WEBHOOK_ID in entry.data and cloud.async_active_subscription(hass):
        try:
            _LOGGER.debug(
                "Removing Netatmo cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: NetatmoConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    account = config_entry.runtime_data.account
    # A disabled home leaves the account, so everything below it looks stale to
    # the inventory check. Its descendants keep their own disabler, hence a walk.
    unpolled_home_ids = account.all_home_names.keys() - account.homes.keys()
    device_registry = dr.async_get(hass)
    device: AnyDeviceEntry | None = device_entry
    while device is not None:
        if any(
            identifier[1] in unpolled_home_ids
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        ):
            return False
        parent_id = (
            device.parent_device_id
            if isinstance(device, dr.ChildDeviceEntry)
            else device.via_device_id
        )
        device = (
            device_registry.async_get(parent_id, include_child_devices=False)
            if parent_id
            else None
        )

    homes = config_entry.runtime_data.account.homes.values()
    valid_ids = {
        *config_entry.runtime_data.account.all_home_names,
        *config_entry.runtime_data.account.modules,
        *(module for home in homes for module in home.modules),
        *(room for home in homes for room in home.rooms),
    }

    return not any(
        identifier[1] in valid_ids
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    )
