"""The BLUETTI integration."""

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any

from bluetti_modbus_lib import get_device
from modbus_connection import ModbusTcpParams
from pybluetti import ProductClient, StompClient, UserProduct

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    storage,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .application_credentials import async_ensure_default_credential
from .const import DOMAIN, EVENT_TOKEN_EXPIRED
from .coordinator import BluettiDeviceCoordinator, BluettiModbusCoordinator
from .modbus_support import modbus_dev_type_for_model
from .models import BluettiData
from .oauth import AsyncConfigEntryAuth, AuthTokenRefresh
from .profile.application_profile import APPLICATION_PROFILE

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
    # Defaults empty: local Modbus is optional/opt-in per device, so most
    # entries (and every existing test's BluettiRuntimeData construction)
    # never populate this.
    modbus_coordinators: dict[str, BluettiModbusCoordinator] = field(
        default_factory=dict
    )


type BluettiConfigEntry = ConfigEntry[BluettiRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> bool:
    """Set up BLUETTI from a config entry."""
    try:
        await APPLICATION_PROFILE.load_config(hass)

        enabled_devices = entry.options.get("devices", [])
        all_products_data: list[dict[str, Any]] = entry.data.get("products", [])
        all_products: list[UserProduct] = [
            UserProduct.model_validate(p) if isinstance(p, dict) else p
            for p in all_products_data
        ]

        # OAUTH2: get the access token.
        try:
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, entry
                )
            )
        except ValueError:
            # The OAuth2 implementation is resolved from the BLUETTI
            # Application Credential in HA storage. If that credential was
            # ever lost (e.g. a partial backup restore, or an entry that was
            # created without going through the config flow), setup would
            # otherwise fail with this same error forever. Re-import the
            # credential (a no-op if it's already there) and retry once
            # before giving up.
            __LOGGER__.warning(
                "BLUETTI OAuth implementation not found, re-importing the "
                "default credential and retrying"
            )
            await async_ensure_default_credential(hass)
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, entry
                )
            )
        __LOGGER__.debug("OAuth implementation is: %s", implementation.__class__)

        http_session = async_get_clientsession(hass)
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
        auth = AsyncConfigEntryAuth(http_session, oauth_session)

        # Must run before AuthTokenRefresh.start_token_check() below: that
        # call's is_token_valid() check reads oauth_session.token
        # synchronously, as-is - a normally-expired access token with a
        # still-valid refresh token would otherwise show the user a false
        # "OAuth expired" notification/issue on every setup, moments before
        # this call transparently refreshes it.
        await oauth_session.async_ensure_token_valid()
        access_token = oauth_session.token["access_token"]

        auth_token_refresh = AuthTokenRefresh(hass, entry, oauth_session)
        auth_token_refresh.start_token_check()
        product_client = ProductClient(
            http_session,
            APPLICATION_PROFILE.config["server"]["gateway"],
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
        APPLICATION_PROFILE.config["server"]["wss"],
        access_token,
        bluetti_devices.web_socket_message_handler,
        on_auth_expired=lambda: hass.bus.fire(EVENT_TOKEN_EXPIRED),
    )
    # Registered before connect() even starts, not after setup fully
    # succeeds: if a later step below (e.g. a device's first refresh) raises
    # ConfigEntryNotReady, Home Assistant still runs already-registered
    # async_on_unload callbacks before retrying setup - without this, each
    # retry would connect a new client without ever disconnecting the
    # previous attempt's.
    entry.async_on_unload(stomp_client.disconnect)
    # connect() retries internally with its own exponential backoff on
    # failure (see pybluetti's StompClient.reconnect) rather than raising -
    # awaiting it directly here would block this entire setup (and the REST
    # polling fallback it's meant to be independent of) until it eventually
    # succeeds, possibly indefinitely. A background task tied to the entry's
    # lifecycle means a slow or unavailable WSS endpoint never delays or
    # blocks the cloud coordinators below from being set up.
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

    modbus_coordinators: dict[str, BluettiModbusCoordinator] = {}
    for device in bluetti_devices.devices:
        modbus_config = entry.options.get("modbus", {}).get(device.device_id)
        dev_type = modbus_dev_type_for_model(device.model)
        if not (modbus_config and dev_type):
            continue
        try:
            unit = async_get_unit(
                hass,
                entry,
                ModbusTcpParams(host=modbus_config["host"], port=modbus_config["port"]),
                1,
            )
        except HomeAssistantError as err:
            # Another config entry already holds this host/port with
            # different link settings - local Modbus is optional/
            # supplementary here, so skip just this device's Modbus rather
            # than failing the whole entry over it.
            __LOGGER__.warning(
                "Could not get a Modbus connection for %s: %s", device.device_id, err
            )
            continue
        modbus_device = get_device(dev_type, unit)
        if modbus_device is None:
            continue
        modbus_coordinators[device.device_id] = BluettiModbusCoordinator(
            hass, entry, device.device_id, modbus_device
        )

    # Local Modbus is optional/supplementary - async_refresh() (not
    # async_config_entry_first_refresh()) never raises ConfigEntryNotReady,
    # so a device that doesn't answer just leaves that device's Modbus
    # entities unavailable until the coordinator's own next poll succeeds,
    # instead of failing the whole entry (and its cloud entities) too.
    # Matches home-assistant/core's fronius integration, which uses the same
    # async_refresh()-not-first_refresh() pattern for its own optional
    # secondary Modbus coordinators.
    await asyncio.gather(
        *(coordinator.async_refresh() for coordinator in modbus_coordinators.values())
    )

    entry.runtime_data = BluettiRuntimeData(
        auth=auth,
        bluetti_devices=bluetti_devices,
        stomp_client=stomp_client,
        coordinators=coordinators,
        modbus_coordinators=modbus_coordinators,
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
    # No explicit cleanup calls here: the websocket is disconnected by the
    # async_on_unload callback registered right after it connects in
    # async_setup_entry (so a failed setup retry cleans it up too, not just
    # a full unload). DataUpdateCoordinator (constructed with
    # config_entry=entry) already registers its own async_shutdown via
    # config_entry.async_on_unload, and the shared Modbus connection is
    # released the same way - async_get_unit (see modbus_coordinator.py)
    # registers its own release callback via entry.async_on_unload when the
    # unit is first acquired.
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
            modbus_coordinator = runtime_data.modbus_coordinators.pop(device_id, None)
            if modbus_coordinator:
                # This stops the coordinator's own polling, but - unlike the
                # HACS build's BluettiModbusClient-owned connection - it does
                # NOT release the underlying shared Modbus connection: that
                # release callback was registered on the whole config entry
                # by async_get_unit, not per device, so it only runs when the
                # entry itself unloads. A device removed here leaves its
                # connection open (unused) until then - a characteristic of
                # async_get_unit's entry-scoped release, not a leak specific
                # to this integration.
                await modbus_coordinator.async_shutdown()

    current_devices = entry.options.get("devices", [])
    new_devices = [d for d in current_devices if d not in device_ids]
    current_modbus = entry.options.get("modbus", {})
    new_modbus = {sn: cfg for sn, cfg in current_modbus.items() if sn not in device_ids}

    # Also drop the removed device(s)' cached product entries from
    # entry.data["products"] - a later re-add of the same serial is
    # treated as "already cached" by config_flow.py/options_flow.py's
    # product merge (they only add products whose sn isn't already
    # present) and would otherwise silently keep serving this now-stale
    # name/model/state instead of the fresh data the re-add just fetched
    # from the cloud.
    current_products = entry.data.get("products", [])
    new_products = [
        p
        for p in current_products
        if (p.get("sn") if isinstance(p, dict) else p.sn) not in device_ids
    ]

    if (
        new_devices != current_devices
        or new_modbus != current_modbus
        or new_products != current_products
    ):
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "products": new_products},
            options={**entry.options, "devices": new_devices, "modbus": new_modbus},
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

    # No explicit device/entity registry cleanup here: ConfigEntries.async_remove
    # already calls device_registry.async_clear_config_entry() and
    # entity_registry.async_clear_config_entry() right after this hook returns.
    # Doing it here too was not just redundant but unsafe - async_remove_device()
    # deletes the device outright, which is wrong for a device merged with
    # another integration's device (a composite device ID), unlike the
    # registries' own clear_config_entry(), which only clears this entry's
    # association.
    store: storage.Store[Any] = storage.Store(
        hass, 1, f"{DOMAIN}_data_{entry.entry_id}.json"
    )
    await store.async_remove()
