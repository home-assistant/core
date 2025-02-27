"""Support for Automation Device Specification (ADS).

Set up the ADS component and provide functionality for reading symbols,
monitoring ADS connection, and writing data by name.
"""

import asyncio  # Added for async operations
from asyncio import Task
import logging
from typing import Any

import pyads
import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADS_STATEMAP,
    ADS_TYPEMAP,
    CONF_ADS_AMSNETID,
    CONF_ADS_APPTIMESTAMP,
    CONF_ADS_FIELDS,
    CONF_ADS_HUB,
    CONF_ADS_HUB_DEFAULT,
    CONF_ADS_NAME,
    CONF_ADS_RETRY,
    CONF_ADS_SYMBOLS,
    CONF_ADS_TEMPLATE,
    CONF_ADS_TIMEOUT,
    CONF_ADS_TYPE,
    CONF_ADS_VALUE,
    CONF_ADS_VAR,
    DOMAIN,
    SERVICE_WRITE_DATA_BY_NAME,
    AdsBinarySensorKeys,
    AdsClimateKeys,
    AdsCoverKeys,
    AdsDefaultTemplate,
    AdsLightKeys,
    AdsSensorKeys,
    AdsState,
    AdsSwitchKeys,
    AdsType,
    AdsValveKeys,
)
from .hub import AdsHub

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_DEVICE): cv.string,
                        vol.Required(CONF_PORT, default=851): cv.port,
                        vol.Optional(CONF_IP_ADDRESS): cv.string,
                        vol.Optional(CONF_ADS_AMSNETID): cv.string,
                        vol.Optional(CONF_ADS_HUB): cv.string,
                        vol.Optional(CONF_ADS_TIMEOUT, default=5): cv.positive_int,
                        vol.Optional(CONF_ADS_RETRY, default=15): cv.positive_int,
                        vol.Optional(CONF_ADS_TEMPLATE, default={}): vol.Schema(
                            {
                                vol.Optional(
                                    AdsLightKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_LIGHT,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsLightKeys.VAR,
                                                    default=AdsDefaultTemplate.VAR_STATE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAR_BRIGHTNESS,
                                                    default=AdsDefaultTemplate.VAR_BRIGHTNESS,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAL_MIN_BRIGHTNESS,
                                                    default=AdsDefaultTemplate.VAL_MIN_BRIGHTNESS,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsLightKeys.VAL_MAX_BRIGHTNESS,
                                                    default=AdsDefaultTemplate.VAL_MAX_BRIGHTNESS,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsLightKeys.VAR_COLOR_TEMP_KELVIN,
                                                    default=AdsDefaultTemplate.VAR_COLOR_TEMP_KELVIN,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAL_MIN_COLOR_TEMP_KELVIN,
                                                    default=AdsDefaultTemplate.VAL_MIN_COLOR_TEMP_KELVIN,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsLightKeys.VAL_MAX_COLOR_TEMP_KELVIN,
                                                    default=AdsDefaultTemplate.VAL_MAX_COLOR_TEMP_KELVIN,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsLightKeys.VAR_HUE,
                                                    default=AdsDefaultTemplate.VAR_HUE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAR_SATURATION,
                                                    default=AdsDefaultTemplate.VAR_SATURATION,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAR_COLOR_MODE,
                                                    default=AdsDefaultTemplate.VAR_COLOR_MODE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.TYPE,
                                                    default=AdsDefaultTemplate.TYPE_UNSIGNED_INTEGER,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.TYPE_MODE,
                                                    default=AdsDefaultTemplate.TYPE_UNSIGNED_INTEGER,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsLightKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                                vol.Optional(
                                    AdsSwitchKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_SWITCH,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsSwitchKeys.VAR,
                                                    default=AdsDefaultTemplate.VAR_STATE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSwitchKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSwitchKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSwitchKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                                vol.Optional(
                                    AdsClimateKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_CLIMATE,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsClimateKeys.VAR_CURRENT_TEMPERATURE,
                                                    default=AdsDefaultTemplate.VAR_TEMP,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.VAR_TARGET_TEMPERATURE,
                                                    default=AdsDefaultTemplate.VAR_SET_TEMP,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.VAL_MIN_TEMPERATURE,
                                                    default=AdsDefaultTemplate.VAL_MIN_TEMP,
                                                ): vol.Coerce(float),
                                                vol.Optional(
                                                    AdsClimateKeys.VAL_MAX_TEMPERATURE,
                                                    default=AdsDefaultTemplate.VAL_MAX_TEMP,
                                                ): vol.Coerce(float),
                                                vol.Optional(
                                                    AdsClimateKeys.UNIT_OF_MEASUREMENT,
                                                    default=AdsDefaultTemplate.UNIT_OF_TEMPERATURE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.VAR_HVAC_MODE,
                                                    default=AdsDefaultTemplate.VAR_HVAC_MODE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.FACTOR,
                                                    default=AdsDefaultTemplate.VAL_FACTOR,
                                                ): vol.Any(None, cv.positive_int),
                                                vol.Optional(
                                                    AdsClimateKeys.TYPE,
                                                    default=AdsDefaultTemplate.TYPE_FLOAT,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.TYPE_MODE,
                                                    default=AdsDefaultTemplate.TYPE_UNSIGNED_INTEGER,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsClimateKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                                vol.Optional(
                                    AdsCoverKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_COVER,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsCoverKeys.VAR,
                                                    default=AdsDefaultTemplate.VAR_IS_CLOSED,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_POSITION,
                                                    default=AdsDefaultTemplate.VAR_POSITION,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_SET_POSITION,
                                                    default=AdsDefaultTemplate.VAR_SET_POSITION,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAL_OPEN_POSITION,
                                                    default=AdsDefaultTemplate.VAL_OPEN_POSITION,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsCoverKeys.VAL_CLOSE_POSITION,
                                                    default=AdsDefaultTemplate.VAL_CLOSE_POSITION,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_TILT,
                                                    default=AdsDefaultTemplate.VAR_TILT,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_SET_TILT,
                                                    default=AdsDefaultTemplate.VAR_SET_TILT,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAL_OPEN_TILT,
                                                    default=AdsDefaultTemplate.VAL_OPEN_TILT,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsCoverKeys.VAL_CLOSE_TILT,
                                                    default=AdsDefaultTemplate.VAL_CLOSE_TILT,
                                                ): vol.Coerce(int),
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_OPEN,
                                                    default=AdsDefaultTemplate.VAR_OPEN,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_CLOSE,
                                                    default=AdsDefaultTemplate.VAR_CLOSE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_STOP,
                                                    default=AdsDefaultTemplate.VAR_STOP,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_OPEN_TILT,
                                                    default=AdsDefaultTemplate.VAR_OPEN_TILT,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_CLOSE_TILT,
                                                    default=AdsDefaultTemplate.VAR_CLOSE_TILT,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.TYPE,
                                                    default=AdsDefaultTemplate.TYPE_UNSIGNED_INTEGER,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsCoverKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                                vol.Optional(
                                    AdsSensorKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_SENSOR,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsSensorKeys.VAR,
                                                    default=AdsDefaultTemplate.VAR_VALUE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSensorKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSensorKeys.TYPE,
                                                    default=AdsDefaultTemplate.TYPE_FLOAT,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSensorKeys.FACTOR,
                                                    default=AdsDefaultTemplate.VAL_FACTOR,
                                                ): vol.Any(None, cv.positive_int),
                                                vol.Optional(
                                                    AdsSensorKeys.STATE_CLASS,
                                                    default=AdsDefaultTemplate.STATE_CLASS,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSensorKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsSensorKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                                vol.Optional(
                                    AdsBinarySensorKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_BINARY_SENSOR,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsBinarySensorKeys.VAR,
                                                    default=AdsDefaultTemplate.VAR_STATE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsBinarySensorKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsBinarySensorKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsBinarySensorKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                                vol.Optional(
                                    AdsValveKeys.PLATFORM, default={}
                                ): vol.Schema(
                                    {
                                        vol.Optional(
                                            CONF_ADS_NAME,
                                            default=AdsDefaultTemplate.STRUCT_VALVE,
                                        ): cv.string,
                                        vol.Optional(
                                            CONF_ADS_FIELDS, default={}
                                        ): vol.Schema(
                                            {
                                                vol.Optional(
                                                    AdsValveKeys.VAR,
                                                    default=AdsDefaultTemplate.VAR_STATE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsValveKeys.VAR_NAME,
                                                    default=AdsDefaultTemplate.VAR_NAME,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsValveKeys.VAR_DEVICE_TYPE,
                                                    default=AdsDefaultTemplate.VAR_DEVICE_TYPE,
                                                ): cv.string,
                                                vol.Optional(
                                                    AdsValveKeys.VAR_ERROR,
                                                    default=AdsDefaultTemplate.VAR_ERROR,
                                                ): cv.string,
                                            }
                                        ),
                                    }
                                ),
                            }
                        ),
                    }
                )
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component.

    Initialize ADS hubs, register services, and start monitoring tasks.

    """
    conf_list = config[DOMAIN]
    monitoring_tasks: dict[str, Task] = {}
    hub_index = 0

    for conf in conf_list:
        device = conf[CONF_DEVICE]
        port = conf[CONF_PORT]
        ip_address = conf.get(CONF_IP_ADDRESS)
        hub_name = conf.get(CONF_ADS_HUB)
        amsnetid = conf.get(CONF_ADS_AMSNETID)
        timeout = conf.get(CONF_ADS_TIMEOUT)
        retry = conf.get(CONF_ADS_RETRY)
        template = conf.get(CONF_ADS_TEMPLATE)
        hub_index += 1

        if not hub_name:
            hub_name = f"HUB{hub_index}"

        hub_key = f"{DOMAIN}_{hub_name}"

        if hub_key in hass.data:
            _LOGGER.error("%s Hub with name %s already exists", DOMAIN, hub_name)
            continue

        if amsnetid:
            pyads.open_port()
            pyads.set_local_address(amsnetid)

        local_amsnetid = pyads.get_local_address()
        _LOGGER.info("[%s] Read Local AMS-Net-ID %s", hub_name, local_amsnetid.netid)

        try:
            client = pyads.Connection(device, port, ip_address)
            client.open()
            client.set_timeout(timeout * 1000)
        except pyads.ADSError as err:
            _LOGGER.error(
                "[%s] Could not create ADS connection (netid=%s, ip=%s, port=%s): %s",
                hub_name,
                device,
                ip_address,
                port,
                err,
            )
            continue

        try:
            ads = AdsHub(client)
            ads.connection_params = {
                CONF_DEVICE: device,
                CONF_IP_ADDRESS: ip_address,
                CONF_PORT: port,
                CONF_ADS_AMSNETID: amsnetid,
                CONF_ADS_HUB: hub_name,
                CONF_ADS_TIMEOUT: timeout,
                CONF_ADS_RETRY: retry,
            }

            hass.data[hub_key] = ads
            _LOGGER.info(
                "[%s] Connected to ADS host (netid=%s, ip=%s, port=%s)",
                hub_name,
                device,
                ip_address,
                port,
            )
        except pyads.ADSError as err:
            _LOGGER.error(
                "[%s] Could not connect to ADS host (netid=%s, ip=%s, port=%s): %s",
                hub_name,
                device,
                ip_address,
                port,
                err,
            )
            continue

        process_and_pass_symbols_to_platforms(hass, ads, template, config)
        start_monitoring_task(hass, ads, monitoring_tasks)

        def stop_task_listener(event: Event, ads_hub: AdsHub = ads) -> None:
            stop_monitoring_task(ads_hub, monitoring_tasks)

        def shutdown_listener(event: Event, ads_hub: AdsHub = ads) -> None:
            ads_hub.shutdown(True)

        hass.bus.listen(EVENT_HOMEASSISTANT_STOP, stop_task_listener)
        hass.bus.listen(EVENT_HOMEASSISTANT_STOP, shutdown_listener)

    async def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the selected ADS device."""
        hub_name: str = call.data[CONF_ADS_HUB]
        ads_var: str = call.data[CONF_ADS_VAR]
        ads_type: AdsType = call.data[CONF_ADS_TYPE]
        value: str = call.data[CONF_ADS_VALUE]

        hub_key = f"{DOMAIN}_{hub_name}"
        ads = hass.data.get(hub_key)

        if not ads:
            _LOGGER.error(
                "%s Hub with name %s not found. Please select a valid %s",
                DOMAIN,
                hub_name,
                CONF_ADS_HUB,
            )
            return

        try:
            converted_value = convert_value(ads_type, value)
            ads.write_by_name(ads_var, converted_value, ADS_TYPEMAP[ads_type])
        except ValueError as err:
            _LOGGER.error("[%s] Value conversion error: %s", hub_name, err)
        except pyads.ADSError as err:
            _LOGGER.error("[%s] Error writing to ADS variable: %s", hub_name, err)

    def async_register_service() -> None:
        """Register the write_data_by_name service."""
        hass.services.async_register(
            DOMAIN,
            SERVICE_WRITE_DATA_BY_NAME,
            handle_write_data_by_name,
            schema=vol.Schema(
                {
                    vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
                    vol.Required(CONF_ADS_VAR): cv.string,
                    vol.Required(CONF_ADS_TYPE): vol.In(
                        [ads_type.value for ads_type in AdsType]
                    ),
                    vol.Required(CONF_ADS_VALUE): cv.string,
                }
            ),
        )

    def convert_value(ads_type: AdsType, value: str) -> Any:
        """Convert a value to the appropriate type based on AdsType.

        Raises:
            ValueError: If the value cannot be converted.

        """
        if ads_type == AdsType.BOOL:
            value_normalized = value.strip().lower()
            return value_normalized in {"true", "1", "yes"}
        if ads_type in {
            AdsType.BYTE,
            AdsType.INT,
            AdsType.UINT,
            AdsType.SINT,
            AdsType.USINT,
            AdsType.DINT,
            AdsType.UDINT,
            AdsType.WORD,
            AdsType.DWORD,
        }:
            try:
                return int(value)
            except ValueError as err:
                raise ValueError(f"Invalid value for {ads_type}: {value}") from err
        if ads_type in {AdsType.REAL, AdsType.LREAL}:
            try:
                return float(value)
            except ValueError as err:
                raise ValueError(f"Invalid value for {ads_type}: {value}") from err
        if ads_type == AdsType.STRING:
            return str(value)
        if ads_type in {
            AdsType.TIME,
            AdsType.DATE,
            AdsType.DATE_AND_TIME,
            AdsType.TOD,
        }:
            # Conversion to specific formats can be added here.
            return str(value)

        raise ValueError(f"Unsupported AdsType: {ads_type}")

    hass.loop.call_soon_threadsafe(async_register_service)
    return True


def start_monitoring_task(
    hass: HomeAssistant, ads: AdsHub, monitoring_tasks: dict
) -> None:
    """Start the monitoring task for the given ADS hub.

    Initialize and store a monitoring task for the ADS connection.

    """
    hub_name = ads.connection_params.get(CONF_ADS_HUB)
    hub_key = f"{DOMAIN}_{hub_name}"

    if hub_key in monitoring_tasks:
        _LOGGER.warning("[%s] Monitoring task is already running", hub_name)
        return

    try:
        monitoring_task = hass.loop.create_task(monitor_task(ads))
        monitoring_tasks[hub_key] = monitoring_task
        _LOGGER.info("[%s] Monitoring task started", hub_name)
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("[%s] Failed to start monitoring task: %s", hub_name, str(e))


def stop_monitoring_task(ads: AdsHub, monitoring_tasks: dict) -> None:
    """Stop the monitoring task for the given ADS hub.

    Retrieve and cancel the monitoring task if it exists.

    """
    hub_name = ads.connection_params.get(CONF_ADS_HUB)
    hub_key = f"{DOMAIN}_{hub_name}"

    monitoring_task = monitoring_tasks.pop(hub_key, None)
    if monitoring_task:
        if not monitoring_task.done():
            monitoring_task.cancel()
            _LOGGER.info("[%s] Monitoring task stopped", hub_name)
        else:
            _LOGGER.warning("[%s] Monitoring task was already stopped", hub_name)
    else:
        _LOGGER.warning("[%s] No monitoring task found to stop", hub_name)


def process_and_pass_symbols_to_platforms(
    hass: HomeAssistant, ads, template, config
) -> None:
    """Read symbols from the PLC, filter them based on configured PLC types, and pass the filtered symbols to the platforms.

    Args:
        hass: Home Assistant instance.
        ads: ADS component used for reading symbols.
        template: Dictionary of configured PLC types.
        config: Home Assistant configuration.

    """
    symbols = ads.read_all_symbols(template)
    hub_name = ads.connection_params.get(CONF_ADS_HUB)

    if symbols is None or any(value is None for value in symbols.values()):
        _LOGGER.warning(
            "[%s] Some symbol values are None. Aborting processing", hub_name
        )
        return

    if any(symbols.values()):
        for platform, platform_template in template.items():
            platform_symbols = symbols.get(platform)
            if platform_symbols:
                hass.helpers.discovery.load_platform(
                    platform,
                    DOMAIN,
                    {
                        CONF_ADS_HUB: hub_name,
                        CONF_ADS_SYMBOLS: platform_symbols,
                        CONF_ADS_TEMPLATE: platform_template,
                    },
                    config,
                )
    else:
        _LOGGER.warning(
            "[%s] No symbols matched the configured PLC types. No entities will be created",
            hub_name,
        )


async def monitor_task(ads: AdsHub) -> None:
    """Monitor the ADS connection asynchronously and ensure it remains healthy.

    Reinitialize the connection if lost and resume operations.

    Args:
        ads: The AdsHub instance to monitor.

    """

    prevapptimestamp = None
    connected = False  # Track the connection status
    initialized = False  # Track if connection was established at least once
    hub_name = ads.connection_params.get(CONF_ADS_HUB)
    retry_time = int(ads.connection_params.get(CONF_ADS_RETRY, 15))
    check_time = 1
    sleep = int(check_time)

    try:
        while True:
            try:
                state = ads.read_state()
                healthy_state = (
                    state is not None and state[0] == ADS_STATEMAP[AdsState.RUN]
                )
                timestamp_changed = False
                if healthy_state:
                    apptimestamp = ads.read_by_name(
                        CONF_ADS_APPTIMESTAMP, ADS_TYPEMAP[AdsType.DATE_AND_TIME]
                    )
                    timestamp_changed = prevapptimestamp != apptimestamp
                    prevapptimestamp = apptimestamp
                if healthy_state and timestamp_changed and initialized:
                    _LOGGER.warning(
                        "[%s] AdsState: [%s] Build-Timestamp changed to: %s",
                        hub_name,
                        AdsState.RUN,
                        apptimestamp,
                    )
                    healthy_state = False
                    sleep = check_time

                if connected and not healthy_state:
                    connected = False
                    sleep = check_time
                    try:
                        ads.shutdown(clear_temp=False)
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.error("[%s] Error during ADS shutdown: %s", hub_name, e)
                    await asyncio.sleep(sleep)
                    continue

                if not healthy_state and not connected and not initialized:
                    _LOGGER.error(
                        "[%s] ADS connection could not be initialized. Cancelling monitoring task",
                        hub_name,
                    )
                    raise asyncio.CancelledError  # noqa: TRY301

                if not healthy_state and not connected and initialized:
                    sleep = retry_time
                    try:
                        ads.reconnect()
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.error("[%s] Error during ADS restart: %s", hub_name, e)
                    await asyncio.sleep(sleep)
                    continue

                if healthy_state and not connected and initialized:
                    sleep = check_time
                    try:
                        ads.reinitialize_notifications()
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.error(
                            "[%s] Failed to reinitialize notifications: %s", hub_name, e
                        )
                    connected = True
                elif healthy_state and not connected and not initialized:
                    sleep = check_time
                    connected = True
                    initialized = True

            except pyads.ADSError as ads_err:
                _LOGGER.error(
                    "[%s] ADS-specific error in monitoring loop: %s", hub_name, ads_err
                )
            except Exception as e:  # noqa: BLE001
                _LOGGER.error(
                    "[%s] Unexpected error in ADS monitoring loop: %s", hub_name, e
                )

            await asyncio.sleep(sleep)
    except asyncio.CancelledError:
        # Handle cancellation gracefully if the task is cancelled.
        pass
