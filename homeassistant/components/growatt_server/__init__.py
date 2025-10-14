"""The Growatt server PV inverter sensor integration."""

from collections.abc import Mapping
from datetime import datetime
import logging

import growattServer
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    HomeAssistantError,
)
from homeassistant.helpers import selector

from .const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    BATT_MODE_MAP,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    PLATFORMS,
)
from .coordinator import GrowattConfigEntry, GrowattCoordinator
from .models import GrowattRuntimeData

_LOGGER = logging.getLogger(__name__)


def get_device_list_classic(
    api: growattServer.GrowattApi, config: Mapping[str, str]
) -> tuple[list[dict[str, str]], str]:
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    try:
        login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
        # DEBUG: Log the actual response structure
    except Exception as ex:
        _LOGGER.error("DEBUG - Login response: %s", login_response)
        raise ConfigEntryError(
            f"Error communicating with Growatt API during login: {ex}"
        ) from ex

    if not login_response.get("success"):
        msg = login_response.get("msg", "Unknown error")
        _LOGGER.debug("Growatt login failed: %s", msg)
        if msg == LOGIN_INVALID_AUTH_CODE:
            raise ConfigEntryAuthFailed("Username, Password or URL may be incorrect!")
        raise ConfigEntryError(f"Growatt login failed: {msg}")

    user_id = login_response["user"]["id"]

    if plant_id == DEFAULT_PLANT_ID:
        try:
            plant_info = api.plant_list(user_id)
        except Exception as ex:
            raise ConfigEntryError(
                f"Error communicating with Growatt API during plant list: {ex}"
            ) from ex
        if not plant_info or "data" not in plant_info or not plant_info["data"]:
            raise ConfigEntryError("No plants found for this account.")
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of devices for specified plant to add sensors for.
    try:
        devices = api.device_list(plant_id)
    except Exception as ex:
        raise ConfigEntryError(
            f"Error communicating with Growatt API during device list: {ex}"
        ) from ex

    return devices, plant_id


def get_device_list_v1(
    api, config: Mapping[str, str]
) -> tuple[list[dict[str, str]], str]:
    """Device list logic for Open API V1.

    Note: Plant selection (including auto-selection if only one plant exists)
    is handled in the config flow before this function is called. This function
    only fetches devices for the already-selected plant_id.
    """
    plant_id = config[CONF_PLANT_ID]
    try:
        devices_dict = api.device_list(plant_id)
    except growattServer.GrowattV1ApiError as e:
        raise ConfigEntryError(
            f"API error during device list: {e} (Code: {getattr(e, 'error_code', None)}, Message: {getattr(e, 'error_msg', None)})"
        ) from e
    devices = devices_dict.get("devices", [])
    # Only MIN device (type = 7) support implemented in current V1 API
    supported_devices = [
        {
            "deviceSn": device.get("device_sn", ""),
            "deviceType": "min",
        }
        for device in devices
        if device.get("type") == 7
    ]

    for device in devices:
        if device.get("type") != 7:
            _LOGGER.warning(
                "Device %s with type %s not supported in Open API V1, skipping",
                device.get("device_sn", ""),
                device.get("type"),
            )
    return supported_devices, plant_id


def get_device_list(
    api, config: Mapping[str, str], api_version: str
) -> tuple[list[dict[str, str]], str]:
    """Dispatch to correct device list logic based on API version."""
    if api_version == "v1":
        return get_device_list_v1(api, config)
    if api_version == "classic":
        return get_device_list_classic(api, config)
    raise ConfigEntryError(f"Unknown API version: {api_version}")


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Set up Growatt from a config entry."""

    config = config_entry.data
    url = config.get(CONF_URL, DEFAULT_URL)

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        url = DEFAULT_URL
        new_data = dict(config_entry.data)
        new_data[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Determine API version
    if config.get(CONF_AUTH_TYPE) == AUTH_API_TOKEN:
        api_version = "v1"
        token = config[CONF_TOKEN]
        api = growattServer.OpenApiV1(token=token)
    elif config.get(CONF_AUTH_TYPE) == AUTH_PASSWORD:
        api_version = "classic"
        username = config[CONF_USERNAME]
        api = growattServer.GrowattApi(
            add_random_user_id=True, agent_identifier=username
        )
        api.server_url = url
    else:
        raise ConfigEntryError("Unknown authentication type in config entry.")

    devices, plant_id = await hass.async_add_executor_job(
        get_device_list, api, config, api_version
    )

    # Create a coordinator for the total sensors
    total_coordinator = GrowattCoordinator(
        hass, config_entry, plant_id, "total", plant_id
    )

    # Create coordinators for each device
    device_coordinators = {
        device["deviceSn"]: GrowattCoordinator(
            hass, config_entry, device["deviceSn"], device["deviceType"], plant_id
        )
        for device in devices
        if device["deviceType"] in ["inverter", "tlx", "storage", "mix", "min"]
    }

    # Perform the first refresh for the total coordinator
    await total_coordinator.async_config_entry_first_refresh()

    # Perform the first refresh for each device coordinator
    for device_coordinator in device_coordinators.values():
        await device_coordinator.async_config_entry_first_refresh()

    # Store runtime data in the config entry
    config_entry.runtime_data = GrowattRuntimeData(
        total_coordinator=total_coordinator,
        devices=device_coordinators,
    )

    # Set up all the entities
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register services for MIN/TLX devices
    await _async_register_services(hass, config_entry, device_coordinators)

    return True


async def _async_register_services(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    device_coordinators: dict,
) -> None:
    """Register services for MIN/TLX devices."""
    # Get all MIN coordinators with V1 API - single source of truth
    min_coordinators = {
        coord.device_id: coord
        for coord in device_coordinators.values()
        if coord.device_type == "min" and coord.api_version == "v1"
    }

    if not min_coordinators:
        _LOGGER.debug(
            "No MIN devices with V1 API found, skipping TOU service registration. "
            "Services require MIN devices with token authentication"
        )
        return

    _LOGGER.info(
        "Found %d MIN device(s) with V1 API, registering TOU services",
        len(min_coordinators),
    )

    def get_coordinator(device_id: str | None = None) -> GrowattCoordinator:
        """Get coordinator by device_id with consistent behavior."""
        if device_id is None:
            if len(min_coordinators) == 1:
                # Only one device - return it
                return next(iter(min_coordinators.values()))
            # Multiple devices - require explicit selection
            device_list = ", ".join(min_coordinators.keys())
            raise HomeAssistantError(
                f"Multiple MIN devices available ({device_list}). "
                "Please specify device_id parameter."
            )

        # Explicit device_id provided
        if device_id not in min_coordinators:
            raise HomeAssistantError(f"MIN device '{device_id}' not found")

        return min_coordinators[device_id]

    async def handle_update_time_segment(call: ServiceCall) -> None:
        """Handle update_time_segment service call."""
        segment_id = call.data["segment_id"]
        batt_mode_str = str(call.data["batt_mode"])
        start_time_str = call.data["start_time"]
        end_time_str = call.data["end_time"]
        enabled = call.data["enabled"]
        device_id = call.data.get("device_id")

        _LOGGER.debug(
            "handle_update_time_segment: segment_id=%d, batt_mode=%s, start=%s, end=%s, enabled=%s, device_id=%s",
            segment_id,
            batt_mode_str,
            start_time_str,
            end_time_str,
            enabled,
            device_id,
        )

        # Convert batt_mode string to integer
        batt_mode = BATT_MODE_MAP.get(batt_mode_str)
        if batt_mode is None:
            _LOGGER.error("Invalid battery mode: %s", batt_mode_str)
            raise HomeAssistantError(f"Invalid battery mode: {batt_mode_str}")

        # Convert time strings to datetime.time objects
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError as err:
            _LOGGER.error("Start_time and end_time must be in HH:MM format")
            raise HomeAssistantError(
                "start_time and end_time must be in HH:MM format"
            ) from err

        # Get the appropriate MIN coordinator
        coordinator = get_coordinator(device_id)

        try:
            await coordinator.update_time_segment(
                segment_id,
                batt_mode,
                start_time,
                end_time,
                enabled,
            )
        except Exception as err:
            _LOGGER.error(
                "Error updating time segment %d: %s",
                segment_id,
                err,
            )
            raise HomeAssistantError(
                f"Error updating time segment {segment_id}: {err}"
            ) from err

    async def handle_read_time_segments(call: ServiceCall) -> dict:
        """Handle read_time_segments service call."""
        # Get the appropriate MIN coordinator
        coordinator = get_coordinator(call.data.get("device_id"))

        try:
            time_segments = await coordinator.read_time_segments()
        except Exception as err:
            _LOGGER.error("Error reading time segments: %s", err)
            raise HomeAssistantError(f"Error reading time segments: {err}") from err
        else:
            return {"time_segments": time_segments}

    # Create device selector schema helper
    device_selector_fields = {}
    if len(min_coordinators) > 1:
        device_options = [
            selector.SelectOptionDict(value=device_id, label=f"MIN Device {device_id}")
            for device_id in min_coordinators
        ]
        device_selector_fields[vol.Required("device_id")] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=device_options)
        )

    # Define service schemas
    update_schema_fields = {
        vol.Required("segment_id"): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=9, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required("batt_mode"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value="load-first", label="Load First"),
                    selector.SelectOptionDict(
                        value="battery-first", label="Battery First"
                    ),
                    selector.SelectOptionDict(value="grid-first", label="Grid First"),
                ]
            )
        ),
        vol.Required("start_time"): selector.TimeSelector(),
        vol.Required("end_time"): selector.TimeSelector(),
        vol.Required("enabled"): selector.BooleanSelector(),
        **device_selector_fields,
    }

    read_schema_fields = {**device_selector_fields}

    # Register services
    services_to_register = [
        (
            "update_time_segment",
            handle_update_time_segment,
            update_schema_fields,
        ),
        ("read_time_segments", handle_read_time_segments, read_schema_fields),
    ]

    for service_name, handler, schema_fields in services_to_register:
        if not hass.services.has_service(DOMAIN, service_name):
            schema = vol.Schema(schema_fields) if schema_fields else None
            supports_response = (
                SupportsResponse.ONLY
                if service_name == "read_time_segments"
                else SupportsResponse.NONE
            )

            hass.services.async_register(
                DOMAIN,
                service_name,
                handler,
                schema=schema,
                supports_response=supports_response,
            )
            _LOGGER.info("Registered service: %s", service_name)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
