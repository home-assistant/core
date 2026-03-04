"""ISEO Argo BLE Lock — Home Assistant integration."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.ec import SECP224R1, derive_private_key

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import ConfigType

from iseo_argo_ble import IseoAuthError, IseoClient, IseoConnectionError, UserSubType

from .const import (
    CONF_ADDRESS,
    CONF_PRIV_SCALAR,
    CONF_USER_SUBTYPE,
    CONF_UUID,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import IseoLogCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

type IseoConfigEntry = ConfigEntry[IseoRuntimeData]


class IseoRuntimeData:
    """Runtime data for an ISEO Argo BLE config entry."""

    def __init__(
        self,
        coordinator: IseoLogCoordinator,
        priv: object,
    ) -> None:
        """Initialize runtime data."""
        self.coordinator = coordinator
        self.priv = priv


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ISEO Argo BLE Lock component."""

    async def _client_for_entry(config_entry_id: str) -> IseoClient:
        """Resolve a config entry by ID and return a ready IseoClient."""
        entry: IseoConfigEntry | None = hass.config_entries.async_get_entry(
            config_entry_id
        )
        if entry is None or entry.domain != DOMAIN:
            raise vol.Invalid(f"Config entry {config_entry_id!r} not found.")
        if not hasattr(entry, "runtime_data"):
            raise vol.Invalid(f"ISEO lock {config_entry_id!r} is not loaded.")

        priv = entry.runtime_data.priv
        return IseoClient(
            address=entry.data[CONF_ADDRESS],
            uuid_bytes=bytes.fromhex(entry.data[CONF_UUID]),
            identity_priv=priv,
            subtype=entry.data.get(CONF_USER_SUBTYPE, DEFAULT_USER_SUBTYPE),
            ble_device=async_ble_device_from_address(
                hass, entry.data[CONF_ADDRESS], connectable=True
            ),
        )

    async def handle_read_users(call: ServiceCall) -> dict:
        """Fetch the complete list of registered users from the lock."""
        client = await _client_for_entry(call.data["config_entry_id"])
        users = await client.read_users()
        return {
            "users": [
                {
                    "uuid": u.uuid_hex.upper(),
                    "name": u.name,
                    "type": u.user_type,
                    "subtype": u.inner_subtype,
                }
                for u in users
            ]
        }

    async def handle_delete_user(call: ServiceCall) -> None:
        """Remove a user from the lock's whitelist."""
        target_uuid_hex = call.data["uuid"]
        client = await _client_for_entry(call.data["config_entry_id"])

        users = await client.read_users()
        target_user = next(
            (u for u in users if u.uuid_hex.lower() == target_uuid_hex.lower()),
            None,
        )

        if not target_user:
            raise vol.Invalid(f"User with UUID {target_uuid_hex} not found on lock.")

        subtype = target_user.inner_subtype or UserSubType.BT_SMARTPHONE

        await client.erase_user_by_uuid(
            uuid_bytes=bytes.fromhex(target_uuid_hex),
            user_type=target_user.user_type,
            subtype=subtype,
        )

    _ENTRY_ID_SCHEMA = {vol.Required("config_entry_id"): cv.string}

    hass.services.async_register(
        DOMAIN,
        "read_users",
        handle_read_users,
        schema=vol.Schema(_ENTRY_ID_SCHEMA),
        supports_response=entity_platform.SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "delete_user",
        handle_delete_user,
        schema=vol.Schema(
            {
                **_ENTRY_ID_SCHEMA,
                vol.Required("uuid"): cv.string,
            }
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Set up ISEO Argo BLE Lock from a config entry."""
    priv_int = int(entry.data[CONF_PRIV_SCALAR], 16)
    priv = await hass.async_add_executor_job(
        derive_private_key, priv_int, SECP224R1(), default_backend()
    )
    uuid_bytes = bytes.fromhex(entry.data[CONF_UUID])
    subtype: int = entry.data.get(CONF_USER_SUBTYPE, DEFAULT_USER_SUBTYPE)

    coordinator = IseoLogCoordinator(hass, entry, uuid_bytes, priv, subtype)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = IseoRuntimeData(coordinator=coordinator, priv=priv)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Unload a config entry. Best-effort unregister from lock if it's a Gateway."""
    try:
        priv = entry.runtime_data.priv
        address = entry.data[CONF_ADDRESS]
        uuid_bytes = bytes.fromhex(entry.data[CONF_UUID])
        subtype: int = entry.data.get(CONF_USER_SUBTYPE, DEFAULT_USER_SUBTYPE)

        client = IseoClient(
            address=address,
            uuid_bytes=uuid_bytes,
            identity_priv=priv,
            subtype=subtype,
            ble_device=async_ble_device_from_address(
                hass, address, connectable=True
            ),
        )

        if subtype == UserSubType.BT_GATEWAY:
            _LOGGER.debug(
                "Best-effort unregistering gateway from lock %s", address
            )
            async with asyncio.timeout(35):
                await client.erase_user()
    except (IseoConnectionError, IseoAuthError, asyncio.TimeoutError) as exc:
        _LOGGER.debug("Best-effort lock cleanup failed (ignoring): %s", exc)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
