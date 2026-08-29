"""The BLUETTI Cloud integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from pybluetti import ProductClient, StompClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    storage,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .application_credentials import async_ensure_default_credential
from .const import DOMAIN, GATEWAY_URL, WSS_URL, token_expired_signal
from .coordinator import BluettiDeviceCoordinator
from .models import BluettiData
from .oauth import AuthTokenRefresh

__LOGGER__ = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


@dataclass
class BluettiRuntimeData:
    """Runtime data stored on a BLUETTI config entry."""

    bluetti_devices: BluettiData
    stomp_client: StompClient
    coordinators: dict[str, BluettiDeviceCoordinator]


type BluettiConfigEntry = ConfigEntry[BluettiRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> bool:
    """Set up BLUETTI Cloud from a config entry."""
    http_session = async_get_clientsession(hass)
    signal = token_expired_signal(entry.entry_id)

    try:
        # Recovers a restored entry whose Application Credentials storage is
        # missing (e.g. a partial backup restore) - see the function's own
        # docstring for why this must run on every setup, not just the flow.
        await async_ensure_default_credential(hass)
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )

        # pybluetti's clients take a fixed access token at construction, not
        # a live session, so it must be fresh before extracting it below.
        await oauth_session.async_ensure_token_valid()
        access_token = oauth_session.token["access_token"]

        product_client = ProductClient(
            http_session,
            GATEWAY_URL,
            access_token,
            on_auth_expired=lambda: async_dispatcher_send(hass, signal),
        )
        # Batteries included: fetch the account's current device list fresh
        # every setup rather than trusting a cached copy in entry.data - a
        # device added or removed on the cloud side since the last setup is
        # picked up automatically, no separate "add more devices" step.
        products = await product_client.get_user_products()
        if not products.is_ok():
            raise RuntimeError(f"Failed to fetch BLUETTI products: {products}")  # noqa: TRY301
    except OAuth2TokenRequestReauthError as err:
        # Non-recoverable: the refresh token itself is invalid/revoked, so
        # retrying setup would fail identically every time. Needs the user's
        # reauth flow, not ConfigEntryNotReady's endless retry loop.
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="auth_expired"
        ) from err
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    auth_token_refresh = AuthTokenRefresh(hass, entry, oauth_session)
    all_products = products.data or []
    bluetti_devices = BluettiData(hass, all_products)

    # Refreshed on every setup, purely as a fingerprint for the reauth
    # "is this still the same account" safety check in config_flow.py - not
    # a selection list, every product above is always bound and added.
    device_sns = [p.sn for p in all_products]
    if entry.data.get("device_sns") != device_sns:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "device_sns": device_sns}
        )

    # Register WebSocket
    stomp_client = StompClient(
        http_session,
        WSS_URL,
        access_token,
        bluetti_devices.web_socket_message_handler,
        on_auth_expired=lambda: async_dispatcher_send(hass, signal),
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

    # Assigned before the first refresh below, not after: a device already
    # unbound in the cloud triggers _handle_unbind() during that refresh,
    # which needs runtime_data to exist to remove the device - otherwise
    # it's set up anyway once this entry's runtime_data is assigned.
    entry.runtime_data = BluettiRuntimeData(
        bluetti_devices=bluetti_devices,
        stomp_client=stomp_client,
        coordinators=coordinators,
    )

    # Captured before the gather below, not read from coordinators
    # afterward: a device unbound during its own first refresh pops itself
    # out of this same dict (see BluettiDevice._handle_unbind) while the
    # gather is still running, which would otherwise make this list drift
    # out of step with results mid-flight.
    device_ids = list(coordinators)

    # Each device's first refresh is an independent network round-trip, so
    # run them concurrently instead of one-by-one - otherwise setup time
    # scales linearly with the number of devices on the account.
    #
    # return_exceptions=True so one device failing doesn't leave the other
    # devices' refreshes running as orphaned, uncancelled tasks in the
    # background - plain gather() propagates the first exception without
    # waiting for (or cancelling) the rest.
    results = await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ),
        return_exceptions=True,
    )
    for device_id, result in zip(device_ids, results, strict=True):
        if isinstance(result, ConfigEntryAuthFailed):
            # The token is shared by every device on the account - one
            # device reporting it invalid means all of them are, so there's
            # no point limping along with the others.
            raise result
        if isinstance(result, BaseException):
            __LOGGER__.warning(
                "Initial refresh failed for device %s, entities will start "
                "unavailable and it will keep retrying on its own schedule: %s",
                device_id,
                result,
            )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    auth_token_refresh.start_token_check()

    __LOGGER__.info("bluetti_cloud init ok")

    return True


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
    to that device's entities) on its own. Batteries-included means there is
    no persisted device list to drop this device from - if it's still bound
    on the BLUETTI account, the next setup fetches it fresh and re-adds it,
    the same as any other cloud-hub integration with no per-device opt-out.
    Unbind it from the account itself (in the BLUETTI app) for a removal
    that survives a reload.
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
