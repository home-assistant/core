"""ISEO Argo BLE Lock — Home Assistant integration."""

import asyncio
from dataclasses import dataclass
import logging

from cryptography.hazmat.primitives.asymmetric.ec import SECP224R1, derive_private_key
from iseo_argo_ble import IseoClient
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADMIN_USER_SUBTYPE,
    ATTR_ENABLED,
    CONF_ADMIN_PRIV_SCALAR,
    CONF_ADMIN_UUID,
    CONF_PRIV_SCALAR,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
    PLATFORMS,
    SERVICE_DELETE_CREDENTIAL,
    SERVICE_SET_CREDENTIAL_ENABLED,
)
from .coordinator import IseoUserCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions."""
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_CREDENTIAL_ENABLED,
        # Suspending or restoring a credential changes who can get into the
        # house, so it is kept to administrators.
        admin_only=True,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema={vol.Required(ATTR_ENABLED): cv.boolean},
        func="async_set_enabled",
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_CREDENTIAL,
        # Removing a credential cannot be undone from Home Assistant: the
        # person has to enrol theirs again with the Master Card.
        admin_only=True,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="async_delete_credential",
    )
    return True


@dataclass
class IseoData:
    """Runtime data for an ISEO Argo BLE lock."""

    client: IseoClient
    # One BLE radio path to one lock: every operation takes this first.
    ble_lock: asyncio.Lock
    # Only set when the admin identity was enrolled during setup.
    user_coordinator: IseoUserCoordinator | None


type IseoConfigEntry = ConfigEntry[IseoData]


async def async_setup_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Set up ISEO Argo BLE Lock from a config entry."""
    address = entry.data[CONF_ADDRESS]
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"address": address},
        )

    priv_int = int(entry.data[CONF_PRIV_SCALAR], 16)
    priv = await hass.async_add_executor_job(derive_private_key, priv_int, SECP224R1())
    uuid_bytes = bytes.fromhex(entry.data[CONF_UUID])

    client = IseoClient(
        address=address,
        uuid_bytes=uuid_bytes,
        identity_priv=priv,
        subtype=DEFAULT_USER_SUBTYPE,
        ble_device=ble_device,
    )

    ble_lock = asyncio.Lock()
    user_coordinator: IseoUserCoordinator | None = None

    if (admin_uuid := entry.data.get(CONF_ADMIN_UUID)) and (
        admin_scalar := entry.data.get(CONF_ADMIN_PRIV_SCALAR)
    ):
        admin_priv = await hass.async_add_executor_job(
            derive_private_key, int(admin_scalar, 16), SECP224R1()
        )
        admin_client = IseoClient(
            address=address,
            uuid_bytes=bytes.fromhex(admin_uuid),
            identity_priv=admin_priv,
            subtype=ADMIN_USER_SUBTYPE,
            ble_device=ble_device,
        )
        user_coordinator = IseoUserCoordinator(hass, entry, admin_client, ble_lock)

    entry.runtime_data = IseoData(
        client=client,
        ble_lock=ble_lock,
        user_coordinator=user_coordinator,
    )

    if user_coordinator is not None:
        # Deliberately not async_config_entry_first_refresh(): that turns any
        # failure into ConfigEntryNotReady, which would hold up the lock over
        # an optional capability and then retry the admin session on a
        # schedule. Repeated admin reads are the one thing that must never
        # happen to this lock. The credential entities simply do not appear,
        # and the next successful action or reload brings them back.
        await user_coordinator.async_refresh()
        if not user_coordinator.last_update_success:
            _LOGGER.warning(
                "Could not read the credentials enrolled on %s, continuing "
                "without them: %s",
                address,
                user_coordinator.last_exception,
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
