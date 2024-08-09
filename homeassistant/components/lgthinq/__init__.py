# SPDX-FileCopyrightText: Copyright 2024 LG Electronics Inc.
# SPDX-License-Identifier: LicenseRef-LGE-Proprietary

"""Support for LG ThinQ Connect device."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import Any

from aiowebostv import WebOsClient, WebOsTvPairError
import voluptuous as vol

from homeassistant.components import notify as hass_notify
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_SECRET,
    CONF_COUNTRY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceRegistry,
    async_entries_for_config_entry,
    async_get as async_get_device_registry,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BUTTON,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    CONF_CONNECT_CLIENT_ID,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_SOUNDBAR,
    CONF_ENTRY_TYPE_THINQ,
    CONF_ENTRY_TYPE_WEBOSTV,
    DATA_CONFIG_ENTRY_WEBOSTV,
    DATA_HASS_CONFIG,
    DEFAULT_COUNTRY,
    DOMAIN,
    SERVICE_ATTR_DEVICE_INFO,
    SERVICE_ATTR_RESULT,
    SERVICE_ATTR_VALUE,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
    SERVICE_SELECT_SOUND_OUTPUT,
    WEBOSTV_EXCEPTIONS,
    ThinqConfigEntry,
    ThinqData,
)
from .device import LGDevice, async_setup_lg_device
from .mqtt import ThinQMQTT
from .soundbar_client import config_connect
from .thinq import ThinQ

_LOGGER = logging.getLogger(__name__)

##### common #####


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from discovery or configuration.yaml."""
    # hass.data only using for webostv's DATA_HASS_CONFIG and
    # another data using entry.runtime_data
    hass.data.setdefault(DOMAIN, {})
    return await async_setup_webostv(hass, config)


async def async_setup_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Set up an entry."""
    # init runtime_data
    entry.runtime_data = ThinqData(
        lge_device_map=None,
        lge_devices=None,
        lge_mqtt_clients=None,
        soundbar_client=None,
    )
    if entry.data.get(CONF_ENTRY_TYPE) == CONF_ENTRY_TYPE_THINQ:
        return await async_setup_entry_thinq(hass, entry)

    if entry.data.get(CONF_ENTRY_TYPE) == CONF_ENTRY_TYPE_SOUNDBAR:
        return await async_setup_entry_soundbar(hass, entry)

    if entry.data.get(CONF_ENTRY_TYPE) == CONF_ENTRY_TYPE_WEBOSTV:
        return await async_setup_entry_webostv(hass, entry)

    return False


async def async_unload_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Unload the entry."""
    if entry.data.get(CONF_ENTRY_TYPE) == CONF_ENTRY_TYPE_THINQ:
        return await async_unload_entry_thinq(hass, entry)

    if entry.data.get(CONF_ENTRY_TYPE) == CONF_ENTRY_TYPE_SOUNDBAR:
        return await async_unload_entry_soundbar(hass, entry)

    if entry.data.get(CONF_ENTRY_TYPE) == CONF_ENTRY_TYPE_WEBOSTV:
        return await async_unload_entry_webostv(hass, entry)

    return False


##### thinq #####

THINQ_PLATFORMS = [
    Platform.SWITCH,
]

SERVICE_GET_DEVICE_PROFILE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string}
)

SERVICE_GET_DEVICE_STATUS_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

SERVICE_POST_DEVICE_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(SERVICE_ATTR_VALUE): vol.Any(cv.string, dict),
    }
)


async def async_setup_entry_thinq(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Initialize LG ThinQ Connect."""
    _LOGGER.warning("async_setup_entry.")

    thinq = ThinQ(
        hass=hass,
        client_session=async_get_clientsession(hass),
        country_code=entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY),
        client_id=entry.data.get(CONF_CONNECT_CLIENT_ID),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
    )
    device_registry: DeviceRegistry = async_get_device_registry(hass)

    # Setup and register devices.
    device_entry_map: dict[str, LGDevice] = await async_setup_devices(
        hass, thinq, device_registry, entry.entry_id
    )

    lg_devices: list[LGDevice] = device_entry_map.values()
    # runtime_data for Thinq
    entry.runtime_data.lge_device_map = device_entry_map
    entry.runtime_data.lge_devices = lg_devices

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, THINQ_PLATFORMS)

    # Setup connect-client and subscribe.
    thinq_mqtt = ThinQMQTT(
        hass=hass,
        entry=entry,
        thinq=thinq,
        client_id=entry.data.get(CONF_CONNECT_CLIENT_ID),
    )
    try:
        await thinq_mqtt.async_connect_and_subscribe()
    except (TimeoutError, asyncio.CancelledError) as ex:
        raise ConfigEntryNotReady("Error during setup") from ex

    # runtime_data for Thinq
    entry.runtime_data.lge_mqtt_clients = thinq_mqtt

    # Clean up device_registry.
    async_cleanup_device_registry(lg_devices, device_registry, entry.entry_id)

    # Setup services.
    async_setup_hass_services(hass, entry)

    return True


async def async_setup_devices(
    hass: HomeAssistant,
    thinq: ThinQ,
    device_registry: DeviceRegistry,
    entry_id: str,
) -> dict[str, LGDevice]:
    """Set up and register devices."""
    _LOGGER.warning("async_setup_devices.")

    # Get a device list from the server.
    device_list: list[dict] = await thinq.async_get_device_list()
    if not device_list:
        return {}

    # Setup devices.
    lg_device_list: list[LGDevice] = []
    task_list = [
        hass.async_create_task(async_setup_lg_device(hass, thinq, device))
        for device in device_list
    ]
    if task_list:
        task_result = await asyncio.gather(*task_list)
        for lg_device in task_result:
            if lg_device:
                lg_device_list.extend(lg_device)

    # Register devices.
    device_entry_map: dict[str, LGDevice] = {}
    if lg_device_list:
        for lg_device in lg_device_list:
            device_entry: DeviceEntry = device_registry.async_get_or_create(
                config_entry_id=entry_id,
                **lg_device.device_info,
            )
            _LOGGER.debug(
                "Create device_registry. device_id=%s, device_entry_id=%s",
                lg_device.id,
                device_entry.id,
            )
            device_entry_map[device_entry.id] = lg_device

    return device_entry_map


@callback
def async_cleanup_device_registry(
    lg_devices: list[LGDevice],
    device_registry: DeviceRegistry,
    entry_id: str,
) -> None:
    """Clean up device registry."""
    new_device_unique_ids: list[str] = [device.unique_id for device in lg_devices]
    existing_entries: list[DeviceEntry] = async_entries_for_config_entry(
        device_registry, entry_id
    )

    # Remove devices that are no longer exist.
    for old_entry in existing_entries:
        old_unique_id = next(iter(old_entry.identifiers))[1]
        if old_unique_id not in new_device_unique_ids:
            device_registry.async_remove_device(old_entry.id)
            _LOGGER.warning("Remove device_registry. device_id=%s", old_entry.id)


async def _async_get_device_profile(
    entry: ThinqConfigEntry, device_id: str
) -> dict[str, Any] | None:
    if device_id is not None:
        device_entry_map: dict[str, LGDevice] = entry.runtime_data.lge_device_map
    if device_entry_map:
        device = device_entry_map.get(device_id)
        if device is not None:
            return await device.async_get_device_profile()
    return None


async def _async_get_device_status(
    entry: ThinqConfigEntry, device_id: str
) -> dict[str, Any] | None:
    if device_id is not None:
        device_entry_map: dict[str, LGDevice] = entry.runtime_data.lge_device_map
        if device_entry_map:
            device = device_entry_map.get(device_id)
            if device is not None:
                return await device.async_get_device_status()
    return None


async def _async_post_device_status(
    entry: ThinqConfigEntry, device_id: str, value: Any
) -> dict[str, Any] | None:
    if device_id is not None:
        device_entry_map: dict[str, LGDevice] = entry.runtime_data.lge_device_map
        if device_entry_map:
            device = device_entry_map.get(device_id)
            if device is not None:
                return await device.async_post_device_status(value)
    return None


@callback
def async_setup_hass_services(hass: HomeAssistant, entry: ThinqConfigEntry) -> None:
    """Set up services."""

    async def async_handle_reload_device_list(call: ServiceCall) -> None:
        """Handle 'reload_device_list' service call."""
        _LOGGER.debug("async_handle_reload_device_list.")
        await hass.config_entries.async_reload(entry.entry_id)

    async def async_handle_refresh_device_status(call: ServiceCall) -> None:
        """Handle 'refresh_device_status' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        _LOGGER.debug("async_handle_refresh_device_status. device_id=%s", device_id)

        device_entry_map: dict[str, LGDevice] = entry.runtime_data.lge_device_map
        if device_entry_map:
            if device_id is None:
                # If device_id is not specified, refresh for all devices.
                task_list = [
                    hass.async_create_task(device.coordinator.async_refresh())
                    for device in device_entry_map.values()
                ]
                await asyncio.gather(*task_list)
            else:
                target_device: LGDevice = device_entry_map.get(device_id)
                if target_device is not None:
                    await target_device.coordinator.async_refresh()

    async def async_handle_get_device_profile(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle 'get_device_profile' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        device: LGDevice = None
        result: str | dict[str, Any] = None

        _LOGGER.debug("async_handle_get_device_profile. device_id=%s", device_id)

        result = await _async_get_device_profile(entry, device_id)

        return async_create_service_response(
            device_id=device_id, device=device, result=result
        )

    async def async_handle_get_device_status(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle 'get_device_status' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        device: LGDevice = None
        result: str | dict[str, Any] = None

        _LOGGER.debug("async_handle_get_device_status. device_id=%s", device_id)

        result = await _async_get_device_status(entry, device_id)

        return async_create_service_response(
            device_id=device_id, device=device, result=result
        )

    async def async_handle_post_device_status(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle 'post_device_status' service call."""
        device_id: str = call.data.get(ATTR_DEVICE_ID)
        value: Any = call.data.get(SERVICE_ATTR_VALUE)
        device: LGDevice = None
        result: str | dict[str, Any] = None

        _LOGGER.debug(
            "async_handle_post_device_status. device_id=%s, value=%s",
            device_id,
            value,
        )

        result = await _async_post_device_status(entry, device_id, value)

        return async_create_service_response(
            device_id=device_id, device=device, result=result
        )

    hass.services.async_register(
        domain=DOMAIN,
        service="reload_device_list",
        service_func=async_handle_reload_device_list,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="refresh_device_status",
        service_func=async_handle_refresh_device_status,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="get_device_profile",
        service_func=async_handle_get_device_profile,
        schema=SERVICE_GET_DEVICE_PROFILE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="get_device_status",
        service_func=async_handle_get_device_status,
        schema=SERVICE_GET_DEVICE_STATUS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="post_device_status",
        service_func=async_handle_post_device_status,
        schema=SERVICE_POST_DEVICE_STATUS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def async_create_service_response(
    device_id: str | None = None,
    device: LGDevice | None = None,
    result: str | dict[str, Any] | None = None,
) -> ServiceResponse:
    """Create a service response from the result of service call."""
    if result is None:
        if device_id is None:
            result = "error: No device_id specified."
        elif device is None:
            result = "error: Device not found."
        else:
            result = "error: Operation failed."

    return {
        ATTR_DEVICE_ID: device_id,
        SERVICE_ATTR_DEVICE_INFO: (device.device_info if device is not None else None),
        SERVICE_ATTR_RESULT: result,
    }


async def async_unload_entry_thinq(
    hass: HomeAssistant, entry: ThinqConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.warning("async_unload_entry.")
    thinq_mqtt = entry.runtime_data.lge_mqtt_clients
    if thinq_mqtt:
        await thinq_mqtt.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, THINQ_PLATFORMS)


##### Soundbar #####

SOUNDBAR_PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry_soundbar(
    hass: HomeAssistant, entry: ThinqConfigEntry
) -> bool:
    """Seutp an entry for soundbar."""
    _LOGGER.warning("async_setup_entry_soundbar.")

    soundbar_client = await hass.async_add_executor_job(
        config_connect, entry.data[CONF_HOST], entry.data[CONF_PORT]
    )
    if soundbar_client is None:
        raise ConfigEntryError

    hass.async_add_executor_job(soundbar_client.listen)
    # runtime_data for soundbar
    entry.runtime_data.soundbar_client = soundbar_client
    await hass.config_entries.async_forward_entry_setups(entry, SOUNDBAR_PLATFORMS)
    return True


async def async_unload_entry_soundbar(
    hass: HomeAssistant, entry: ThinqConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, SOUNDBAR_PLATFORMS)


##### webOS TV #####

WEBOS_PLATFORMS = [Platform.MEDIA_PLAYER]
CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

BUTTON_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_BUTTON): cv.string})

COMMAND_SCHEMA = CALL_SCHEMA.extend(
    {vol.Required(ATTR_COMMAND): cv.string, vol.Optional(ATTR_PAYLOAD): dict}
)

SOUND_OUTPUT_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_SOUND_OUTPUT): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_BUTTON: {"method": "async_button", "schema": BUTTON_SCHEMA},
    SERVICE_COMMAND: {"method": "async_command", "schema": COMMAND_SCHEMA},
    SERVICE_SELECT_SOUND_OUTPUT: {
        "method": "async_select_sound_output",
        "schema": SOUND_OUTPUT_SCHEMA,
    },
}


async def async_setup_webostv(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LG WebOS TV platform."""
    _LOGGER.warning("async_setup_webostv. config: %s", config)
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY_WEBOSTV, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    return True


async def async_setup_entry_webostv(
    hass: HomeAssistant, entry: ThinqConfigEntry
) -> bool:
    """Set up LG WebOS TV platform config entry."""
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY_WEBOSTV, {})

    host = entry.data[CONF_HOST]
    key = entry.data[CONF_CLIENT_SECRET]

    # Attempt a connection, but fail gracefully if tv is off for example.
    client = WebOsClient(host, key)
    with suppress(*WEBOSTV_EXCEPTIONS):
        try:
            await client.connect()
        except WebOsTvPairError as err:
            raise ConfigEntryError(err) from err

    # If pairing request accepted there will be no error
    # Update the stored key
    update_client_key(hass, entry, client)

    async def async_service_handler(service: ServiceCall) -> None:
        method = SERVICE_TO_METHOD[service.service]
        data = service.data.copy()
        data["method"] = method["method"]
        async_dispatcher_send(hass, DOMAIN, data)

    for service, method in SERVICE_TO_METHOD.items():
        schema = method["schema"]
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )

    hass.data[DOMAIN][DATA_CONFIG_ENTRY_WEBOSTV][entry.entry_id] = client
    await hass.config_entries.async_forward_entry_setups(entry, WEBOS_PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            "notify",
            DOMAIN,
            {
                CONF_NAME: entry.title,
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            },
            hass.data[DOMAIN][DATA_HASS_CONFIG],
        )
    )

    if not entry.update_listeners:
        entry.async_on_unload(entry.add_update_listener(async_update_options))

    async def async_on_stop(_event: Event) -> None:
        """Unregister callbacks and disconnect."""
        client.clear_state_update_callbacks()
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_stop)
    )
    return True


async def async_update_options(hass: HomeAssistant, entry: ThinqConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_control_connect(host: str, key: str | None) -> WebOsClient:
    """LG Connection."""
    client = WebOsClient(host, key)
    try:
        await client.connect()
    except WebOsTvPairError:
        _LOGGER.warning("Connected to LG webOS TV %s but not paired", host)
        raise

    return client


def update_client_key(
    hass: HomeAssistant, entry: ThinqConfigEntry, client: WebOsClient
) -> None:
    """Check and update stored client key if key has changed."""
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_CLIENT_SECRET]

    if client.client_key != key:
        _LOGGER.debug("Updating client key for host %s", host)
        data = {CONF_HOST: host, CONF_CLIENT_SECRET: client.client_key}
        hass.config_entries.async_update_entry(entry, data=data)


async def async_unload_entry_webostv(
    hass: HomeAssistant, entry: ThinqConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, WEBOS_PLATFORMS)

    if unload_ok:
        client = hass.data[DOMAIN][DATA_CONFIG_ENTRY_WEBOSTV].pop(entry.entry_id)
        await hass_notify.async_reload(hass, DOMAIN)
        client.clear_state_update_callbacks()
        await client.disconnect()

    # unregister service calls, check if this is the last entry to unload
    if unload_ok and not hass.data[DOMAIN][DATA_CONFIG_ENTRY_WEBOSTV]:
        for service in SERVICE_TO_METHOD:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok
