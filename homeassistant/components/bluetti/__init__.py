"""The BLUETTI integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from pybluetti import ProductClient, StompClient, UserProduct

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    storage,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, EVENT_TOKEN_EXPIRED, GATEWAY_URL, WSS_URL
from .coordinator import BluettiDeviceCoordinator
from .models import BluettiData
from .oauth import AsyncConfigEntryAuth, AuthTokenRefresh

__LOGGER__ = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


@dataclass
class BluettiRuntimeData:
    """Runtime data stored on a BLUETTI config entry."""

    auth: AsyncConfigEntryAuth
    bluetti_devices: BluettiData
    stomp_client: StompClient
    coordinators: dict[str, BluettiDeviceCoordinator]


type BluettiConfigEntry = ConfigEntry[BluettiRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> bool:
    """Set up BLUETTI from a config entry."""
    try:
        enabled_devices = entry.options.get("devices", [])
        all_products_data: list[dict[str, Any]] = entry.data.get("products", [])
        all_products: list[UserProduct] = [
            UserProduct.model_validate(p) if isinstance(p, dict) else p
            for p in all_products_data
        ]

        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )

        http_session = async_get_clientsession(hass)
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
        auth = AsyncConfigEntryAuth(http_session, oauth_session)

        # pybluetti's clients take a fixed access token at construction, not
        # a live session, so it must be fresh before extracting it below.
        await oauth_session.async_ensure_token_valid()
        access_token = oauth_session.token["access_token"]

        auth_token_refresh = AuthTokenRefresh(hass, entry, oauth_session)
        auth_token_refresh.start_token_check()
        product_client = ProductClient(
            http_session,
            GATEWAY_URL,
            access_token,
            on_auth_expired=lambda: hass.bus.fire(EVENT_TOKEN_EXPIRED),
        )
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    selected_products = [p for p in all_products if p.sn in enabled_devices]

    bluetti_devices = BluettiData(hass, selected_products)

    # Register WebSocket
    stomp_client = StompClient(
        http_session,
        WSS_URL,
        access_token,
        bluetti_devices.web_socket_message_handler,
        on_auth_expired=lambda: hass.bus.fire(EVENT_TOKEN_EXPIRED),
    )
    # Registered before connect() starts, so a setup retry still disconnects it.
    entry.async_on_unload(stomp_client.disconnect)
    # connect() retries forever internally instead of raising (see
    # StompClient.reconnect) - run as a background task so it can't block setup.
    entry.async_create_background_task(
        hass, stomp_client.connect(), f"{DOMAIN}_websocket_connect_{entry.entry_id}"
    )

    coordinators: dict[str, BluettiDeviceCoordinator] = {}
    for device in bluetti_devices.devices:
        device.bind_runtime(product_client, hass, entry)
        coordinators[device.device_id] = BluettiDeviceCoordinator(hass, entry, device)

    # Each device's first refresh is an independent network round-trip, so
    # run them concurrently instead of one-by-one - otherwise setup time
    # scales linearly with the number of devices on the account.
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        )
    )

    entry.runtime_data = BluettiRuntimeData(
        auth=auth,
        bluetti_devices=bluetti_devices,
        stomp_client=stomp_client,
        coordinators=coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Reload the entry when the options flow adds more devices.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    __LOGGER__.info("bluetti init ok")

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: BluettiConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> bool:
    """Unload a config entry."""
    # No explicit cleanup here: the websocket disconnects via the
    # async_on_unload callback registered in async_setup_entry, and each
    # coordinator's async_shutdown is registered via config_entry=entry.
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: BluettiConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Allow removing a single BLUETTI device from an existing entry.

    Home Assistant calls this when the user clicks "Delete" on a device's
    page; returning True lets it sever the device<->entry link (and cascade
    to that device's entities) on its own. This only needs to stop polling
    the device and drop it from the enabled-devices list, so a reload
    doesn't recreate it - the same bookkeeping BluettiDevice._handle_unbind
    does when the cloud reports the device unbound, minus the registry
    cleanup and reload that HA already handles for a user-initiated removal.
    """
    device_ids = {
        identifier
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    }
    if not device_ids:
        return False

    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data:
        runtime_data.bluetti_devices.devices = [
            d
            for d in runtime_data.bluetti_devices.devices
            if d.device_id not in device_ids
        ]
        for device_id in device_ids:
            coordinator = runtime_data.coordinators.pop(device_id, None)
            if coordinator:
                await coordinator.async_shutdown()

    current_devices = entry.options.get("devices", [])
    new_devices = [d for d in current_devices if d not in device_ids]

    # Also drop the cached product entry - a re-add would otherwise reuse
    # this stale name/model instead of fetching fresh data.
    current_products = entry.data.get("products", [])
    new_products = [
        p
        for p in current_products
        if (p.get("sn") if isinstance(p, dict) else p.sn) not in device_ids
    ]

    if new_devices != current_devices or new_products != current_products:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "products": new_products},
            options={**entry.options, "devices": new_devices},
        )

    return True


async def async_remove_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> None:
    """Handle removal of an entry."""
    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data:
        try:
            await runtime_data.stomp_client.disconnect()
        except Exception as e:  # noqa: BLE001 - best-effort disconnect; must not block unload/removal
            __LOGGER__.warning("Error while disconnecting websocket: %s", e)

    # No registry cleanup here - ConfigEntries.async_remove already calls
    # device_registry/entity_registry's async_clear_config_entry() safely.
    store: storage.Store[Any] = storage.Store(
        hass, 1, f"{DOMAIN}_data_{entry.entry_id}.json"
    )
    await store.async_remove()
