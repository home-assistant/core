"""Component to embed Aqualink devices."""

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
import logging
from typing import Any, Concatenate

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLight,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
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


async def async_setup_entry(hass: HomeAssistant, entry: AqualinkConfigEntry) -> bool:
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
    except (AqualinkServiceException, TimeoutError, httpx.HTTPError) as aio_exception:
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
    except (AqualinkServiceException, TimeoutError, httpx.HTTPError) as svc_exception:
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
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
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
                device_registry.async_update_device(
                    device_id=device_entry.id,
                    remove_config_entry_id=entry.entry_id,
                )
            break

    for system in systems_list:
        coordinator = AqualinkDataUpdateCoordinator(hass, entry, system)
        runtime_data.coordinators[system.serial] = coordinator

        prefix = f"{system.serial}_"
        known_devices: set[str] = set()
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
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

    _async_cleanup_stale_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _expected_platform(dev: AqualinkDevice) -> Platform | None:
    """Return the expected platform for a device based on its type."""
    if isinstance(dev, AqualinkThermostat):
        return Platform.CLIMATE
    if isinstance(dev, AqualinkLight):
        return Platform.LIGHT
    if isinstance(dev, AqualinkSwitch):
        return Platform.SWITCH
    if isinstance(dev, AqualinkBinarySensor):
        return Platform.BINARY_SENSOR
    if isinstance(dev, AqualinkSensor):
        return Platform.SENSOR
    return None


def _async_cleanup_stale_entities(
    hass: HomeAssistant, entry: AqualinkConfigEntry
) -> None:
    """Remove entities whose platform no longer matches the device type."""
    entity_registry = er.async_get(hass)

    # Build mapping of unique_id -> expected platform from current devices.
    expected: dict[str, Platform] = {}
    for coordinator in entry.runtime_data.coordinators.values():
        for dev in coordinator.data.values():
            unique_id = f"{dev.system.serial}_{dev.name}"
            if platform := _expected_platform(dev):
                expected[unique_id] = platform

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.unique_id not in expected:
            continue
        if entity_entry.domain != expected[entity_entry.unique_id]:
            entity_registry.async_remove(entity_entry.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: AqualinkConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.client.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
