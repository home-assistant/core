"""Support for Xiaomi Miio."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from miio import (
    AirFresh,
    AirFreshA1,
    AirFreshT2017,
    AirHumidifier,
    AirHumidifierMiot,
    AirHumidifierMjjsq,
    AirPurifier,
    AirPurifierMiot,
    CleaningDetails,
    CleaningSummary,
    ConsumableStatus,
    Device as MiioDevice,
    DeviceException,
    DNDStatus,
    Fan,
    Fan1C,
    FanMiot,
    FanP5,
    FanZA5,
    RoborockVacuum,
    Timer,
    VacuumStatus,
)
from miio.gateway.gateway import GatewayException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_AVAILABLE,
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
    MODEL_FAN_1C,
    MODEL_FAN_P5,
    MODEL_FAN_P9,
    MODEL_FAN_P10,
    MODEL_FAN_P11,
    MODEL_FAN_ZA5,
    MODELS_AIR_MONITOR,
    MODELS_FAN,
    MODELS_FAN_MIIO,
    MODELS_HUMIDIFIER,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
    MODELS_LIGHT,
    MODELS_PURIFIER_MIOT,
    MODELS_SWITCH,
    MODELS_VACUUM,
    ROBOROCK_GENERIC,
    ROCKROBO_GENERIC,
    AuthException,
    SetupException,
)
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

POLLING_TIMEOUT_SEC = 10
UPDATE_INTERVAL = timedelta(seconds=15)

GATEWAY_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
SWITCH_PLATFORMS = [Platform.SWITCH]
FAN_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
HUMIDIFIER_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.HUMIDIFIER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
LIGHT_PLATFORMS = [Platform.LIGHT]
VACUUM_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.VACUUM,
]
AIR_MONITOR_PLATFORMS = [Platform.AIR_QUALITY, Platform.SENSOR]

MODEL_TO_CLASS_MAP = {
    MODEL_FAN_1C: Fan1C,
    MODEL_FAN_P9: FanMiot,
    MODEL_FAN_P10: FanMiot,
    MODEL_FAN_P11: FanMiot,
    MODEL_FAN_P5: FanP5,
    MODEL_FAN_ZA5: FanZA5,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Xiaomi Miio components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        await async_setup_gateway_entry(hass, entry)
        return True

    return bool(
        entry.data[CONF_FLOW_TYPE] != CONF_DEVICE
        or await async_setup_device_entry(hass, entry)
    )


@callback
def get_platforms(config_entry):
    """Return the platforms belonging to a config_entry."""
    model = config_entry.data[CONF_MODEL]
    flow_type = config_entry.data[CONF_FLOW_TYPE]

    if flow_type == CONF_GATEWAY:
        return GATEWAY_PLATFORMS
    if flow_type == CONF_DEVICE:
        if model in MODELS_SWITCH:
            return SWITCH_PLATFORMS
        if model in MODELS_HUMIDIFIER:
            return HUMIDIFIER_PLATFORMS
        if model in MODELS_FAN:
            return FAN_PLATFORMS
        if model in MODELS_LIGHT:
            return LIGHT_PLATFORMS
        for vacuum_model in MODELS_VACUUM:
            if model.startswith(vacuum_model):
                return VACUUM_PLATFORMS
        for air_monitor_model in MODELS_AIR_MONITOR:
            if model.startswith(air_monitor_model):
                return AIR_MONITOR_PLATFORMS
    _LOGGER.error(
        (
            "Unsupported device found! Please create an issue at "
            "https://github.com/syssi/xiaomi_airpurifier/issues "
            "and provide the following data: %s"
        ),
        model,
    )
    return []


def _async_update_data_default(hass, device):
    async def update():
        """Fetch data from the device using async_add_executor_job."""

        async def _async_fetch_data():
            """Fetch data from the device."""
            async with asyncio.timeout(POLLING_TIMEOUT_SEC):
                state = await hass.async_add_executor_job(device.status)
                _LOGGER.debug("Got new state: %s", state)
                return state

        try:
            return await _async_fetch_data()
        except DeviceException as ex:
            if getattr(ex, "code", None) != -9999:
                raise UpdateFailed(ex) from ex
            _LOGGER.info("Got exception while fetching the state, trying again: %s", ex)
        # Try to fetch the data a second time after error code -9999
        try:
            return await _async_fetch_data()
        except DeviceException as ex:
            raise UpdateFailed(ex) from ex

    return update


@dataclass(frozen=True)
class VacuumCoordinatorData:
    """A class that holds the vacuum data retrieved by the coordinator."""

    status: VacuumStatus
    dnd_status: DNDStatus
    last_clean_details: CleaningDetails
    consumable_status: ConsumableStatus
    clean_history_status: CleaningSummary
    timers: list[Timer]
    fan_speeds: dict[str, int]
    fan_speeds_reverse: dict[int, str]


@dataclass(init=False, frozen=True)
class VacuumCoordinatorDataAttributes:
    """A class that holds attribute names for VacuumCoordinatorData.

    These attributes can be used in methods like `getattr` when a generic solutions is
    needed.
    See homeassistant.components.xiaomi_miio.device.XiaomiCoordinatedMiioEntity
    ._extract_value_from_attribute for
    an example.
    """

    status: str = "status"
    dnd_status: str = "dnd_status"
    last_clean_details: str = "last_clean_details"
    consumable_status: str = "consumable_status"
    clean_history_status: str = "clean_history_status"
    timer: str = "timer"
    fan_speeds: str = "fan_speeds"
    fan_speeds_reverse: str = "fan_speeds_reverse"


def _async_update_data_vacuum(
    hass: HomeAssistant, device: RoborockVacuum
) -> Callable[[], Coroutine[Any, Any, VacuumCoordinatorData]]:
    def update() -> VacuumCoordinatorData:
        timer = []

        # See https://github.com/home-assistant/core/issues/38285 for reason on
        # Why timers must be fetched separately.
        try:
            timer = device.timer()
        except DeviceException as ex:
            _LOGGER.debug(
                "Unable to fetch timers, this may happen on some devices: %s", ex
            )

        fan_speeds = device.fan_speed_presets()

        data = VacuumCoordinatorData(
            device.status(),
            device.dnd_status(),
            device.last_clean_details(),
            device.consumable_status(),
            device.clean_history(),
            timer,
            fan_speeds,
            {v: k for k, v in fan_speeds.items()},
        )

        return data

    async def update_async() -> VacuumCoordinatorData:
        """Fetch data from the device using async_add_executor_job."""

        async def execute_update() -> VacuumCoordinatorData:
            async with asyncio.timeout(POLLING_TIMEOUT_SEC):
                state = await hass.async_add_executor_job(update)
                _LOGGER.debug("Got new vacuum state: %s", state)
                return state

        try:
            return await execute_update()
        except DeviceException as ex:
            if getattr(ex, "code", None) != -9999:
                raise UpdateFailed(ex) from ex
            _LOGGER.info("Got exception while fetching the state, trying again: %s", ex)

        # Try to fetch the data a second time after error code -9999
        try:
            return await execute_update()
        except DeviceException as ex:
            raise UpdateFailed(ex) from ex

    return update_async


async def async_create_miio_device_and_coordinator(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Set up a data coordinator and one miio device to service multiple entities."""
    model: str = entry.data[CONF_MODEL]
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    name = entry.title
    device: MiioDevice | None = None
    migrate = False
    lazy_discover = False
    update_method = _async_update_data_default
    coordinator_class: type[DataUpdateCoordinator[Any]] = DataUpdateCoordinator

    if (
        model not in MODELS_HUMIDIFIER
        and model not in MODELS_FAN
        and model not in MODELS_VACUUM
        and not model.startswith(ROBOROCK_GENERIC)
        and not model.startswith(ROCKROBO_GENERIC)
    ):
        return

    _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

    # Humidifiers
    if model in MODELS_HUMIDIFIER_MIOT:
        device = AirHumidifierMiot(host, token, lazy_discover=lazy_discover)
        migrate = True
    elif model in MODELS_HUMIDIFIER_MJJSQ:
        device = AirHumidifierMjjsq(
            host, token, lazy_discover=lazy_discover, model=model
        )
        migrate = True
    elif model in MODELS_HUMIDIFIER_MIIO:
        device = AirHumidifier(host, token, lazy_discover=lazy_discover, model=model)
        migrate = True
    # Airpurifiers and Airfresh
    elif model in MODELS_PURIFIER_MIOT:
        device = AirPurifierMiot(host, token, lazy_discover=lazy_discover)
    elif model.startswith("zhimi.airpurifier."):
        device = AirPurifier(host, token, lazy_discover=lazy_discover)
    elif model.startswith("zhimi.airfresh."):
        device = AirFresh(host, token, lazy_discover=lazy_discover)
    elif model == MODEL_AIRFRESH_A1:
        device = AirFreshA1(host, token, lazy_discover=lazy_discover)
    elif model == MODEL_AIRFRESH_T2017:
        device = AirFreshT2017(host, token, lazy_discover=lazy_discover)
    elif (
        model in MODELS_VACUUM
        or model.startswith(ROBOROCK_GENERIC)
        or model.startswith(ROCKROBO_GENERIC)
    ):
        # TODO: add lazy_discover as argument when python-miio add support # pylint: disable=fixme
        device = RoborockVacuum(host, token)
        update_method = _async_update_data_vacuum
        coordinator_class = DataUpdateCoordinator[VacuumCoordinatorData]
    # Pedestal fans
    elif model in MODEL_TO_CLASS_MAP:
        device = MODEL_TO_CLASS_MAP[model](host, token, lazy_discover=lazy_discover)
    elif model in MODELS_FAN_MIIO:
        device = Fan(host, token, lazy_discover=lazy_discover, model=model)
    else:
        _LOGGER.error(
            (
                "Unsupported device found! Please create an issue at "
                "https://github.com/syssi/xiaomi_airpurifier/issues "
                "and provide the following data: %s"
            ),
            model,
        )
        return

    if migrate:
        # Removing fan platform entity for humidifiers and migrate the name
        # to the config entry for migration
        entity_registry = er.async_get(hass)
        assert entry.unique_id
        entity_id = entity_registry.async_get_entity_id("fan", DOMAIN, entry.unique_id)
        if entity_id:
            # This check is entities that have a platform migration only
            # and should be removed in the future
            if (entity := entity_registry.async_get(entity_id)) and (
                migrate_entity_name := entity.name
            ):
                hass.config_entries.async_update_entry(entry, title=migrate_entity_name)
            entity_registry.async_remove(entity_id)

    # Create update miio device and coordinator
    coordinator = coordinator_class(
        hass,
        _LOGGER,
        name=name,
        update_method=update_method(hass, device),
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=UPDATE_INTERVAL,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        KEY_DEVICE: device,
        KEY_COORDINATOR: coordinator,
    }

    # Trigger first data fetch
    await coordinator.async_config_entry_first_refresh()


async def async_setup_gateway_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the Xiaomi Gateway component from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    name = entry.title
    gateway_id = entry.unique_id

    assert gateway_id

    # Connect to gateway
    gateway = ConnectXiaomiGateway(hass, entry)
    try:
        await gateway.async_connect_gateway(host, token)
    except AuthException as error:
        raise ConfigEntryAuthFailed() from error
    except SetupException as error:
        raise ConfigEntryNotReady() from error
    gateway_info = gateway.gateway_info

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, gateway_info.mac_address)},
        identifiers={(DOMAIN, gateway_id)},
        manufacturer="Xiaomi",
        name=name,
        model=gateway_info.model,
        sw_version=gateway_info.firmware_version,
        hw_version=gateway_info.hardware_version,
    )

    def update_data_factory(sub_device):
        """Create update function for a subdevice."""

        async def async_update_data():
            """Fetch data from the subdevice."""
            try:
                await hass.async_add_executor_job(sub_device.update)
            except GatewayException as ex:
                _LOGGER.error("Got exception while fetching the state: %s", ex)
                return {ATTR_AVAILABLE: False}
            return {ATTR_AVAILABLE: True}

        return async_update_data

    coordinator_dict: dict[str, DataUpdateCoordinator] = {}
    for sub_device in gateway.gateway_device.devices.values():
        # Create update coordinator
        coordinator_dict[sub_device.sid] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=name,
            update_method=update_data_factory(sub_device),
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=UPDATE_INTERVAL,
        )

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_GATEWAY: gateway.gateway_device,
        KEY_COORDINATOR: coordinator_dict,
    }

    await hass.config_entries.async_forward_entry_setups(entry, GATEWAY_PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))


async def async_setup_device_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Xiaomi Miio device component from a config entry."""
    platforms = get_platforms(entry)
    await async_create_miio_device_and_coordinator(hass, entry)

    if not platforms:
        return False

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = get_platforms(config_entry)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, platforms
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
