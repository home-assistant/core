"""The ViCare integration."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
import logging
import os
from typing import Any

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.components.climate import DOMAIN as DOMAIN_CLIMATE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    DEFAULT_CACHE_DURATION,
    DEVICE_LIST,
    DOMAIN,
    PLATFORMS,
    UNSUPPORTED_DEVICES,
)
from .types import ViCareDevice
from .utils import get_device, get_device_serial

_LOGGER = logging.getLogger(__name__)
_TOKEN_FILENAME = "vicare_token.save"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    try:
        await hass.async_add_executor_job(setup_vicare_api, hass, entry)
    except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    for device in hass.data[DOMAIN][entry.entry_id][DEVICE_LIST]:
        # Migration can be removed in 2025.4.0
        await async_migrate_devices_and_entities(hass, entry, device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def vicare_login(
    hass: HomeAssistant,
    entry_data: Mapping[str, Any],
    cache_duration=DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(cache_duration)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, _TOKEN_FILENAME),
    )
    return vicare_api


def setup_vicare_api(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up PyVicare API."""
    vicare_api = vicare_login(hass, entry.data)

    device_config_list = get_supported_devices(vicare_api.devices)
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        vicare_api = vicare_login(hass, entry.data, cache_duration)
        device_config_list = get_supported_devices(vicare_api.devices)

    for device in device_config_list:
        _LOGGER.debug(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )

    hass.data[DOMAIN][entry.entry_id][DEVICE_LIST] = [
        ViCareDevice(config=device_config, api=get_device(entry, device_config))
        for device_config in device_config_list
    ]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(
            os.remove, hass.config.path(STORAGE_DIR, _TOKEN_FILENAME)
        )

    return unload_ok


async def async_migrate_devices_and_entities(
    hass: HomeAssistant, entry: ConfigEntry, device: ViCareDevice
) -> None:
    """Migrate old entry."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    gateway_serial: str = device.config.getConfig().serial
    device_id = device.config.getId()
    device_serial: str | None = await hass.async_add_executor_job(
        get_device_serial, device.api
    )
    device_model = device.config.getModel()

    old_identifier = gateway_serial
    new_identifier = (
        f"{gateway_serial}_{device_serial if device_serial is not None else device_id}"
    )

    # Migrate devices
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if (
            device_entry.identifiers == {(DOMAIN, old_identifier)}
            and device_entry.model == device_model
        ):
            _LOGGER.debug(
                "Migrating device %s to new identifier %s",
                device_entry.name,
                new_identifier,
            )
            device_registry.async_update_device(
                device_entry.id,
                serial_number=device_serial,
                new_identifiers={(DOMAIN, new_identifier)},
            )

            # Migrate entities
            for entity_entry in er.async_entries_for_device(
                entity_registry, device_entry.id, True
            ):
                if entity_entry.unique_id.startswith(new_identifier):
                    # already correct, nothing to do
                    continue
                unique_id_parts = entity_entry.unique_id.split("-")
                # replace old prefix `<gateway-serial>`
                # with `<gateways-serial>_<device-serial>`
                unique_id_parts[0] = new_identifier
                # convert climate entity unique id
                # from `<device_identifier>-<circuit_no>`
                # to `<device_identifier>-heating-<circuit_no>`
                if entity_entry.domain == DOMAIN_CLIMATE:
                    unique_id_parts[len(unique_id_parts) - 1] = (
                        f"{entity_entry.translation_key}-{unique_id_parts[len(unique_id_parts)-1]}"
                    )
                entity_new_unique_id = "-".join(unique_id_parts)

                _LOGGER.debug(
                    "Migrating entity %s to new unique id %s",
                    entity_entry.name,
                    entity_new_unique_id,
                )
                entity_registry.async_update_entity(
                    entity_id=entity_entry.entity_id, new_unique_id=entity_new_unique_id
                )


def get_supported_devices(
    devices: list[PyViCareDeviceConfig],
) -> list[PyViCareDeviceConfig]:
    """Remove unsupported devices from the list."""
    return [
        device_config
        for device_config in devices
        if device_config.getModel() not in UNSUPPORTED_DEVICES
    ]
