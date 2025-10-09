"""Utils for Comelit."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiocomelit.api import (
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.exceptions import CannotAuthenticate, CannotConnect, CannotRetrieveData
from aiohttp import ClientSession, CookieJar

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)

from .const import _LOGGER, DOMAIN
from .coordinator import ComelitBaseCoordinator
from .entity import ComelitBridgeBaseEntity

DeviceType = ComelitSerialBridgeObject | ComelitVedoAreaObject | ComelitVedoZoneObject


async def async_client_session(hass: HomeAssistant) -> ClientSession:
    """Return a new aiohttp session."""
    return aiohttp_client.async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
    )


def load_api_data(device: ComelitSerialBridgeObject, domain: str) -> list[Any]:
    """Load data from the API."""
    # This function is called when the data is loaded from the API
    if not isinstance(device.val, list):
        raise HomeAssistantError(
            translation_domain=domain, translation_key="invalid_clima_data"
        )
    # CLIMATE has a 2 item tuple:
    # - first  for Clima
    # - second for Humidifier
    return device.val[0] if domain == CLIMATE_DOMAIN else device.val[1]


async def cleanup_stale_entity(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entry_unique_id: str,
    device: ComelitSerialBridgeObject,
) -> None:
    """Cleanup stale entity."""
    entity_reg: er.EntityRegistry = er.async_get(hass)

    identifiers: list[str] = []

    for entry in er.async_entries_for_config_entry(entity_reg, config_entry.entry_id):
        if entry.unique_id == entry_unique_id:
            entry_name = entry.name or entry.original_name
            _LOGGER.info("Removing entity: %s [%s]", entry.entity_id, entry_name)
            entity_reg.async_remove(entry.entity_id)
            identifiers.append(f"{config_entry.entry_id}-{device.type}-{device.index}")

    if len(identifiers) > 0:
        _async_remove_state_config_entry_from_devices(hass, identifiers, config_entry)


def _async_remove_state_config_entry_from_devices(
    hass: HomeAssistant, identifiers: list[str], config_entry: ConfigEntry
) -> None:
    """Remove config entry from device."""

    device_registry = dr.async_get(hass)
    for identifier in identifiers:
        device = device_registry.async_get_device(identifiers={(DOMAIN, identifier)})
        if device:
            _LOGGER.info(
                "Removing config entry %s from device %s",
                config_entry.title,
                device.name,
            )
            device_registry.async_update_device(
                device_id=device.id,
                remove_config_entry_id=config_entry.entry_id,
            )


def bridge_api_call[_T: ComelitBridgeBaseEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Catch Bridge API call exceptions."""

    @wraps(func)
    async def cmd_wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except CannotConnect as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotRetrieveData as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotAuthenticate:
            self.coordinator.last_update_success = False
            self.coordinator.config_entry.async_start_reauth(self.hass)

    return cmd_wrapper


def new_device_listener(
    coordinator: ComelitBaseCoordinator,
    new_devices_callback: Callable[
        [
            list[
                ComelitSerialBridgeObject
                | ComelitVedoAreaObject
                | ComelitVedoZoneObject
            ],
            str,
        ],
        None,
    ],
    data_type: str,
) -> Callable[[], None]:
    """Subscribe to coordinator updates to check for new devices."""
    known_devices: set[int] = set()

    def _check_devices() -> None:
        """Check for new devices and call callback with any new monitors."""
        if not coordinator.data:
            return

        new_devices: list[DeviceType] = []
        for _id in coordinator.data[data_type]:
            if _id not in known_devices:
                known_devices.add(_id)
                new_devices.append(coordinator.data[data_type][_id])

        if new_devices:
            new_devices_callback(new_devices, data_type)

    # Check for devices immediately
    _check_devices()

    return coordinator.async_add_listener(_check_devices)
