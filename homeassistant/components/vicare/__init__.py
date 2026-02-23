"""The ViCare integration."""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
from typing import Any, cast

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.storage import STORAGE_DIR

from .circulation import (
    DhwCirculationBoostState,
    async_activate_dhw_circulation_boost,
    async_get_device_from_call,
)
from .const import (
    CONF_HEAT_TIMEOUT_MINUTES,
    CONF_MIN_BOOST_TEMPERATURE,
    CONF_WARM_WATER_DELAY_MINUTES,
    DEFAULT_CACHE_DURATION,
    DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES,
    DEFAULT_DHW_BOOST_MIN_TEMPERATURE,
    DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES,
    DOMAIN,
    PLATFORMS,
    SERVICE_ACTIVATE_DHW_CIRCULATION_BOOST,
    SERVICE_GET_DEVICE_RAW_FEATURES,
    SERVICE_GET_DHW_CIRCULATION_SCHEDULE,
    UNSUPPORTED_DEVICES,
    VICARE_TOKEN_FILENAME,
)
from .types import ViCareConfigEntry, ViCareData, ViCareDevice
from .utils import get_device, get_device_serial, login

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")
    hass.data.setdefault(DOMAIN, {})
    try:
        entry.runtime_data = await hass.async_add_executor_job(
            setup_vicare_api, hass, entry
        )
    except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    _async_register_services(hass, entry)

    for device in entry.runtime_data.devices:
        # Migration can be removed in 2025.4.0
        await async_migrate_devices_and_entities(hass, entry, device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _async_register_services(hass: HomeAssistant, entry: ViCareConfigEntry) -> None:
    """Register ViCare services once."""
    if hass.data[DOMAIN].get("services_registered"):
        return

    async def async_get_dhw_circulation_schedule(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Return DHW circulation schedule and supported modes."""
        devices = await hass.async_add_executor_job(
            _get_dhw_circulation_schedule_data, entry.runtime_data.devices
        )
        return cast(ServiceResponse, {"devices": devices})

    async def async_get_device_raw_features(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Return raw device data from the ViCare API."""
        devices = await hass.async_add_executor_job(
            _get_device_raw_features_data, entry.runtime_data.devices
        )
        return cast(ServiceResponse, {"devices": devices})

    async def async_activate_dhw_circulation_boost_service(
        call: ServiceCall,
    ) -> None:
        """Activate DHW circulation boost for a device."""
        duration_minutes = int(call.data["duration_minutes"])
        min_storage_temperature = call.data.get("min_storage_temperature")
        min_boost_temperature = call.data.get("min_boost_temperature")
        if min_boost_temperature is None and min_storage_temperature is None:
            min_boost_temperature = entry.options.get(
                CONF_MIN_BOOST_TEMPERATURE, DEFAULT_DHW_BOOST_MIN_TEMPERATURE
            )
        target_setpoint = call.data.get("target_setpoint")
        heat_timeout_minutes = call.data.get(
            "heat_timeout_minutes",
            entry.options.get(
                CONF_HEAT_TIMEOUT_MINUTES, DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES
            ),
        )
        warm_water_delay_minutes = call.data.get(
            "warm_water_delay_minutes",
            entry.options.get(
                CONF_WARM_WATER_DELAY_MINUTES,
                DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES,
            ),
        )
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        device_ids = call.data.get(CONF_DEVICE_ID)
        entity_id = entity_ids[0] if isinstance(entity_ids, list) else entity_ids
        device_id = device_ids[0] if isinstance(device_ids, list) else device_ids

        device = await async_get_device_from_call(
            hass,
            entry.runtime_data.devices,
            entity_id,
            device_id,
        )
        state_map: dict[str, DhwCirculationBoostState] = hass.data[DOMAIN].setdefault(
            "dhw_circulation_boost", {}
        )
        await async_activate_dhw_circulation_boost(
            hass,
            device,
            duration_minutes,
            state_map,
            min_boost_temperature=min_boost_temperature,
            min_storage_temperature=min_storage_temperature,
            target_setpoint=target_setpoint,
            heat_timeout_minutes=heat_timeout_minutes,
            warm_water_delay_minutes=warm_water_delay_minutes,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DHW_CIRCULATION_SCHEDULE,
        async_get_dhw_circulation_schedule,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DEVICE_RAW_FEATURES,
        async_get_device_raw_features,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_DHW_CIRCULATION_BOOST,
        async_activate_dhw_circulation_boost_service,
        schema=vol.Schema(
            {
                vol.Required("duration_minutes"): vol.All(
                    cv.positive_int, vol.Range(min=10, max=240)
                ),
                vol.Optional("min_storage_temperature"): vol.All(
                    vol.Coerce(float), vol.Range(min=20, max=70)
                ),
                vol.Optional("min_boost_temperature"): vol.All(
                    vol.Coerce(float), vol.Range(min=20, max=70)
                ),
                vol.Optional("target_setpoint"): vol.All(
                    vol.Coerce(float), vol.Range(min=30, max=70)
                ),
                vol.Optional("heat_timeout_minutes"): vol.All(
                    cv.positive_int, vol.Range(min=10, max=240)
                ),
                vol.Optional("warm_water_delay_minutes"): vol.All(
                    cv.positive_int, vol.Range(min=1, max=240)
                ),
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.data[DOMAIN]["services_registered"] = True


def _get_dhw_circulation_schedule_data(
    devices: list[ViCareDevice],
) -> list[dict[str, Any]]:
    """Return DHW circulation schedule and supported modes for devices."""
    results: list[dict[str, object]] = []
    for device in devices:
        device_config = device.config
        device_serial = get_device_serial(device.api)
        device_info = {
            "gateway_serial": device_config.getConfig().serial,
            "device_id": device_config.getId(),
            "device_serial": device_serial,
            "device_model": device_config.getModel(),
            "supported": True,
        }

        try:
            schedule = device.api.getDomesticHotWaterCirculationSchedule()
            modes = device.api.getDomesticHotWaterCirculationScheduleModes()
        except PyViCareNotSupportedFeatureError:
            device_info["supported"] = False
            device_info["error"] = "not_supported"
        except PyViCareRateLimitError as err:
            device_info["supported"] = False
            device_info["error"] = f"rate_limited: {err}"
        except PyViCareInvalidDataError as err:
            device_info["supported"] = False
            device_info["error"] = f"invalid_data: {err}"
        except requests.exceptions.ConnectionError:
            device_info["supported"] = False
            device_info["error"] = "connection_error"
        except ValueError:
            device_info["supported"] = False
            device_info["error"] = "decode_error"
        else:
            device_info["schedule"] = schedule
            device_info["schedule_modes"] = modes

        results.append(device_info)
    return results


def _get_device_raw_features_data(
    devices: list[ViCareDevice],
) -> list[dict[str, Any]]:
    """Return raw device data for devices."""
    results: list[dict[str, object]] = []
    for device in devices:
        device_config = device.config
        device_info: dict[str, object] = {
            "gateway_serial": device_config.getConfig().serial,
            "device_id": device_config.getId(),
            "device_model": device_config.getModel(),
        }
        dump = device_config.dump_secure()
        try:
            device_info["raw_features"] = json.loads(dump)
        except json.JSONDecodeError:
            device_info["raw_features"] = dump
        results.append(device_info)
    return results


def setup_vicare_api(hass: HomeAssistant, entry: ViCareConfigEntry) -> PyViCare:
    """Set up PyVicare API."""
    client = login(hass, entry.data)

    device_config_list = get_supported_devices(client.devices)

    # increase cache duration to fit rate limit to number of devices
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        client = login(hass, entry.data, cache_duration)
        device_config_list = get_supported_devices(client.devices)

    for device in device_config_list:
        _LOGGER.debug(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )

    devices = [
        ViCareDevice(config=device_config, api=get_device(entry, device_config))
        for device_config in device_config_list
        if bool(device_config.isOnline())
    ]
    return ViCareData(client=client, devices=devices)


async def async_unload_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(
            os.remove, hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME)
        )

    return unload_ok


async def async_migrate_devices_and_entities(
    hass: HomeAssistant, entry: ViCareConfigEntry, device: ViCareDevice
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
                if entity_entry.domain == CLIMATE_DOMAIN:
                    unique_id_parts[len(unique_id_parts) - 1] = (
                        f"{entity_entry.translation_key}-"
                        f"{unique_id_parts[len(unique_id_parts) - 1]}"
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
