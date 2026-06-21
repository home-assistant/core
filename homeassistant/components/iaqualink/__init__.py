"""Component to embed Aqualink devices."""

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
import logging
from typing import Any, Concatenate

import httpx2
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .const import DOMAIN
from .coordinator import AqualinkDataUpdateCoordinator
from .entity import AqualinkEntity
from .utils import error_detail

_LOGGER = logging.getLogger(__name__)

ATTR_CONFIG = "config"
PARALLEL_UPDATES = 0

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type AqualinkConfigEntry = ConfigEntry[AqualinkRuntimeData]


@dataclass
class AqualinkRuntimeData:
    """Runtime data for Aqualink."""

    client: AqualinkClient
    coordinators: dict[str, AqualinkDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AqualinkConfigEntry) -> None:
    """Set up Aqualink from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    aqualink = AqualinkClient(
        username,
        password,
        httpx_client=get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2),
    )
    try:
        await aqualink.login()
    except AqualinkServiceUnauthorizedException as auth_exception:
        await aqualink.close()
        raise ConfigEntryAuthFailed(
            "Invalid credentials for iAquaLink"
        ) from auth_exception
    except (AqualinkServiceException, TimeoutError, httpx2.HTTPError) as aio_exception:
        await aqualink.close()
        raise ConfigEntryNotReady(
            f"Error while attempting login: {error_detail(aio_exception)}"
        ) from aio_exception

    try:
        systems = await aqualink.get_systems()
    except AqualinkServiceUnauthorizedException as auth_exception:
        await aqualink.close()
        raise ConfigEntryAuthFailed(
            "Invalid credentials for iAquaLink"
        ) from auth_exception
    except (AqualinkServiceException, TimeoutError, httpx2.HTTPError) as svc_exception:
        await aqualink.close()
        raise ConfigEntryNotReady(
            "Error while attempting to retrieve systems list: "
            f"{error_detail(svc_exception)}"
        ) from svc_exception

    systems_list = list(systems.values())
    if not systems_list:
        await aqualink.close()
        raise ConfigEntryError("No systems detected or supported")

    runtime_data = AqualinkRuntimeData(
        aqualink,
        coordinators={},
    )
    device_registry = dr.async_get(hass)

    # Remove devices belonging to systems no longer in the account.
    current_serials = set(systems)
    all_device_entries = [
        *dr.async_entries_for_config_entry(device_registry, entry.entry_id),
        *dr.async_child_entries_for_config_entry(device_registry, entry.entry_id),
    ]
    for device_entry in all_device_entries:
        for domain, identifier in device_entry.identifiers:
            if domain != DOMAIN:
                continue
            # System-level device: identifier is just the serial.
            # Child device: identifier is "{serial}_{name}".
            belongs_to_current = any(
                identifier == s or identifier.startswith(f"{s}_")
                for s in current_serials
            )
            if not belongs_to_current:
                device_registry.async_remove_device(device_entry.id)
            break

    for system in systems_list:
        coordinator = AqualinkDataUpdateCoordinator(hass, entry, system)
        runtime_data.coordinators[system.serial] = coordinator

        prefix = f"{system.serial}_"
        known_devices: set[str] = set()
        for device_entry in all_device_entries:
            for domain, identifier in device_entry.identifiers:
                if domain == DOMAIN and identifier.startswith(prefix):
                    known_devices.add(identifier.removeprefix(prefix))
        coordinator.seed_previous_devices(known_devices)

        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryAuthFailed:
            await aqualink.close()
            raise
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            name=system.name,
            identifiers={(DOMAIN, system.serial)},
            manufacturer="Jandy",
            serial_number=system.serial,
        )

    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AqualinkConfigEntry) -> None:
    """Unload a config entry."""
    await entry.runtime_data.client.close()
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


def refresh_system[_AqualinkEntityT: AqualinkEntity, **_P](
    func: Callable[Concatenate[_AqualinkEntityT, _P], Awaitable[Any]],
) -> Callable[Concatenate[_AqualinkEntityT, _P], Coroutine[Any, Any, None]]:
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(
        self: _AqualinkEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        """Call decorated function and send update signal to all entities."""
        await func(self, *args, **kwargs)
        self.coordinator.async_update_listeners()

    return wrapper
