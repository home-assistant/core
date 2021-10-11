"""The Shelly integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Final, cast

import aioshelly
from aioshelly.block_device import BlockDevice
from aioshelly.rpc_device import RpcDevice
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry, update_coordinator
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    ATTR_GENERATION,
    BATTERY_DEVICES_WITH_PERMANENT_CONNECTION,
    BLOCK,
    CONF_COAP_PORT,
    DATA_CONFIG_ENTRY,
    DEFAULT_COAP_PORT,
    DEVICE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    INPUTS_EVENTS_DICT,
    POLLING_TIMEOUT_SEC,
    REST,
    REST_SENSORS_UPDATE_INTERVAL,
    RPC,
    RPC_INPUTS_EVENTS_TYPES,
    RPC_RECONNECT_INTERVAL,
    SHBTN_MODELS,
    SLEEP_PERIOD_MULTIPLIER,
    UPDATE_PERIOD_MULTIPLIER,
)
from .utils import (
    get_block_device_name,
    get_block_device_sleep_period,
    get_coap_context,
    get_device_entry_gen,
    get_rpc_device_name,
)

BLOCK_PLATFORMS: Final = ["binary_sensor", "cover", "light", "sensor", "switch"]
BLOCK_SLEEPING_PLATFORMS: Final = ["binary_sensor", "sensor"]
RPC_PLATFORMS: Final = ["binary_sensor", "light", "sensor", "switch"]
_LOGGER: Final = logging.getLogger(__name__)

COAP_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_COAP_PORT, default=DEFAULT_COAP_PORT): cv.port,
    }
)
CONFIG_SCHEMA: Final = vol.Schema({DOMAIN: COAP_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Shelly component."""
    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}

    conf = config.get(DOMAIN)
    if conf is not None:
        hass.data[DOMAIN][CONF_COAP_PORT] = conf[CONF_COAP_PORT]

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly from a config entry."""
    # The custom component for Shelly devices uses shelly domain as well as core
    # integration. If the user removes the custom component but doesn't remove the
    # config entry, core integration will try to configure that config entry with an
    # error. The config entry data for this custom component doesn't contain host
    # value, so if host isn't present, config entry will not be configured.
    if not entry.data.get(CONF_HOST):
        _LOGGER.warning(
            "The config entry %s probably comes from a custom integration, please remove it if you want to use core Shelly integration",
            entry.title,
        )
        return False

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = {}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = None

    if get_device_entry_gen(entry) == 2:
        return await async_setup_rpc_entry(hass, entry)

    return await async_setup_block_entry(hass, entry)


async def async_setup_block_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly block based device from a config entry."""
    temperature_unit = "C" if hass.config.units.is_metric else "F"

    options = aioshelly.common.ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        temperature_unit,
    )

    coap_context = await get_coap_context(hass)

    device = await BlockDevice.create(
        aiohttp_client.async_get_clientsession(hass),
        coap_context,
        options,
        False,
    )

    dev_reg = device_registry.async_get(hass)
    device_entry = None
    if entry.unique_id is not None:
        device_entry = dev_reg.async_get_device(
            identifiers={(DOMAIN, entry.unique_id)}, connections=set()
        )
    if device_entry and entry.entry_id not in device_entry.config_entries:
        device_entry = None

    sleep_period = entry.data.get("sleep_period")

    @callback
    def _async_device_online(_: Any) -> None:
        _LOGGER.debug("Device %s is online, resuming setup", entry.title)
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = None

        if sleep_period is None:
            data = {**entry.data}
            data["sleep_period"] = get_block_device_sleep_period(device.settings)
            data["model"] = device.settings["device"]["type"]
            hass.config_entries.async_update_entry(entry, data=data)

        hass.async_create_task(async_block_device_setup(hass, entry, device))

    if sleep_period == 0:
        # Not a sleeping device, finish setup
        _LOGGER.debug("Setting up online block device %s", entry.title)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                await device.initialize()
        except (asyncio.TimeoutError, OSError) as err:
            raise ConfigEntryNotReady from err

        await async_block_device_setup(hass, entry, device)
    elif sleep_period is None or device_entry is None:
        # Need to get sleep info or first time sleeping device setup, wait for device
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = device
        _LOGGER.debug(
            "Setup for device %s will resume when device is online", entry.title
        )
        device.subscribe_updates(_async_device_online)
    else:
        # Restore sensors for sleeping device
        _LOGGER.debug("Setting up offline block device %s", entry.title)
        await async_block_device_setup(hass, entry, device)

    return True


async def async_block_device_setup(
    hass: HomeAssistant, entry: ConfigEntry, device: BlockDevice
) -> None:
    """Set up a block based device that is online."""
    device_wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        BLOCK
    ] = BlockDeviceWrapper(hass, entry, device)
    device_wrapper.async_setup()

    platforms = BLOCK_SLEEPING_PLATFORMS

    if not entry.data.get("sleep_period"):
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
            REST
        ] = ShellyDeviceRestWrapper(hass, device)
        platforms = BLOCK_PLATFORMS

    hass.config_entries.async_setup_platforms(entry, platforms)


async def async_setup_rpc_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly RPC based device from a config entry."""
    options = aioshelly.common.ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )

    _LOGGER.debug("Setting up online RPC device %s", entry.title)
    try:
        async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
            device = await RpcDevice.create(
                aiohttp_client.async_get_clientsession(hass), options
            )
    except (asyncio.TimeoutError, OSError) as err:
        raise ConfigEntryNotReady from err

    device_wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        RPC
    ] = RpcDeviceWrapper(hass, entry, device)
    device_wrapper.async_setup()

    hass.config_entries.async_setup_platforms(entry, RPC_PLATFORMS)

    return True


class BlockDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Shelly block based device with Home Assistant specific functions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device: BlockDevice
    ) -> None:
        """Initialize the Shelly device wrapper."""
        self.device_id: str | None = None
        sleep_period = entry.data["sleep_period"]

        if sleep_period:
            update_interval = SLEEP_PERIOD_MULTIPLIER * sleep_period
        else:
            update_interval = (
                UPDATE_PERIOD_MULTIPLIER * device.settings["coiot"]["update_period"]
            )

        device_name = (
            get_block_device_name(device) if device.initialized else entry.title
        )
        super().__init__(
            hass,
            _LOGGER,
            name=device_name,
            update_interval=timedelta(seconds=update_interval),
        )
        self.hass = hass
        self.entry = entry
        self.device = device

        entry.async_on_unload(
            self.async_add_listener(self._async_device_updates_handler)
        )
        self._last_input_events_count: dict = {}

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)
        )

    @callback
    def _async_device_updates_handler(self) -> None:
        """Handle device updates."""
        if not self.device.initialized:
            return

        assert self.device.blocks

        # For buttons which are battery powered - set initial value for last_event_count
        if self.model in SHBTN_MODELS and self._last_input_events_count.get(1) is None:
            for block in self.device.blocks:
                if block.type != "device":
                    continue

                if len(block.wakeupEvent) == 1 and block.wakeupEvent[0] == "button":
                    self._last_input_events_count[1] = -1

                break

        # Check for input events
        for block in self.device.blocks:
            if (
                "inputEvent" not in block.sensor_ids
                or "inputEventCnt" not in block.sensor_ids
            ):
                continue

            channel = int(block.channel or 0) + 1
            event_type = block.inputEvent
            last_event_count = self._last_input_events_count.get(channel)
            self._last_input_events_count[channel] = block.inputEventCnt

            if (
                last_event_count is None
                or last_event_count == block.inputEventCnt
                or event_type == ""
            ):
                continue

            if event_type in INPUTS_EVENTS_DICT:
                self.hass.bus.async_fire(
                    EVENT_SHELLY_CLICK,
                    {
                        ATTR_DEVICE_ID: self.device_id,
                        ATTR_DEVICE: self.device.settings["device"]["hostname"],
                        ATTR_CHANNEL: channel,
                        ATTR_CLICK_TYPE: INPUTS_EVENTS_DICT[event_type],
                        ATTR_GENERATION: 1,
                    },
                )
            else:
                _LOGGER.warning(
                    "Shelly input event %s for device %s is not supported, please open issue",
                    event_type,
                    self.name,
                )

    async def _async_update_data(self) -> None:
        """Fetch data."""
        if sleep_period := self.entry.data.get("sleep_period"):
            # Sleeping device, no point polling it, just mark it unavailable
            raise update_coordinator.UpdateFailed(
                f"Sleeping device did not update within {sleep_period} seconds interval"
            )

        _LOGGER.debug("Polling Shelly Block Device - %s", self.name)
        try:
            async with async_timeout.timeout(POLLING_TIMEOUT_SEC):
                await self.device.update()
        except OSError as err:
            raise update_coordinator.UpdateFailed("Error fetching data") from err

    @property
    def model(self) -> str:
        """Model of the device."""
        return cast(str, self.entry.data["model"])

    @property
    def mac(self) -> str:
        """Mac address of the device."""
        return cast(str, self.entry.unique_id)

    def async_setup(self) -> None:
        """Set up the wrapper."""
        dev_reg = device_registry.async_get(self.hass)
        sw_version = self.device.firmware_version if self.device.initialized else ""
        entry = dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            name=self.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.mac)},
            manufacturer="Shelly",
            model=aioshelly.const.MODEL_NAMES.get(self.model, self.model),
            sw_version=sw_version,
        )
        self.device_id = entry.id
        self.device.subscribe_updates(self.async_set_updated_data)

    def shutdown(self) -> None:
        """Shutdown the wrapper."""
        self.device.shutdown()

    @callback
    def _handle_ha_stop(self, _event: Event) -> None:
        """Handle Home Assistant stopping."""
        _LOGGER.debug("Stopping BlockDeviceWrapper for %s", self.name)
        self.shutdown()


class ShellyDeviceRestWrapper(update_coordinator.DataUpdateCoordinator):
    """Rest Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass: HomeAssistant, device: BlockDevice) -> None:
        """Initialize the Shelly device wrapper."""
        if (
            device.settings["device"]["type"]
            in BATTERY_DEVICES_WITH_PERMANENT_CONNECTION
        ):
            update_interval = (
                SLEEP_PERIOD_MULTIPLIER * device.settings["coiot"]["update_period"]
            )
        else:
            update_interval = REST_SENSORS_UPDATE_INTERVAL

        super().__init__(
            hass,
            _LOGGER,
            name=get_block_device_name(device),
            update_interval=timedelta(seconds=update_interval),
        )
        self.device = device

    async def _async_update_data(self) -> None:
        """Fetch data."""
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                _LOGGER.debug("REST update for %s", self.name)
                await self.device.update_status()
        except OSError as err:
            raise update_coordinator.UpdateFailed("Error fetching data") from err

    @property
    def mac(self) -> str:
        """Mac address of the device."""
        return cast(str, self.device.settings["device"]["mac"])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if get_device_entry_gen(entry) == 2:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, RPC_PLATFORMS
        )
        if unload_ok:
            await hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][RPC].shutdown()
            hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

        return unload_ok

    device = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id].get(DEVICE)
    if device is not None:
        # If device is present, device wrapper is not setup yet
        device.shutdown()
        return True

    platforms = BLOCK_SLEEPING_PLATFORMS

    if not entry.data.get("sleep_period"):
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][REST] = None
        platforms = BLOCK_PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][BLOCK].shutdown()
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

    return unload_ok


def get_block_device_wrapper(
    hass: HomeAssistant, device_id: str
) -> BlockDeviceWrapper | None:
    """Get a Shelly block device wrapper for the given device id."""
    if not hass.data.get(DOMAIN):
        return None

    dev_reg = device_registry.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            if not hass.data[DOMAIN][DATA_CONFIG_ENTRY].get(config_entry):
                continue

            if wrapper := hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry].get(BLOCK):
                return cast(BlockDeviceWrapper, wrapper)

    return None


def get_rpc_device_wrapper(
    hass: HomeAssistant, device_id: str
) -> RpcDeviceWrapper | None:
    """Get a Shelly RPC device wrapper for the given device id."""
    if not hass.data.get(DOMAIN):
        return None

    dev_reg = device_registry.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            if not hass.data[DOMAIN][DATA_CONFIG_ENTRY].get(config_entry):
                continue

            if wrapper := hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry].get(RPC):
                return cast(RpcDeviceWrapper, wrapper)

    return None


class RpcDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Shelly RPC based device with Home Assistant specific functions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device: RpcDevice
    ) -> None:
        """Initialize the Shelly device wrapper."""
        self.device_id: str | None = None

        device_name = get_rpc_device_name(device) if device.initialized else entry.title
        super().__init__(
            hass,
            _LOGGER,
            name=device_name,
            update_interval=timedelta(seconds=RPC_RECONNECT_INTERVAL),
        )
        self.entry = entry
        self.device = device

        entry.async_on_unload(
            self.async_add_listener(self._async_device_updates_handler)
        )
        self._last_event: dict[str, Any] | None = None

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)
        )

    @callback
    def _async_device_updates_handler(self) -> None:
        """Handle device updates."""
        if (
            not self.device.initialized
            or not self.device.event
            or self.device.event == self._last_event
        ):
            return

        self._last_event = self.device.event

        for event in self.device.event["events"]:
            if event.get("event") not in RPC_INPUTS_EVENTS_TYPES:
                continue

            self.hass.bus.async_fire(
                EVENT_SHELLY_CLICK,
                {
                    ATTR_DEVICE_ID: self.device_id,
                    ATTR_DEVICE: self.device.hostname,
                    ATTR_CHANNEL: event["id"] + 1,
                    ATTR_CLICK_TYPE: event["event"],
                    ATTR_GENERATION: 2,
                },
            )

    async def _async_update_data(self) -> None:
        """Fetch data."""
        if self.device.connected:
            return

        try:
            _LOGGER.debug("Reconnecting to Shelly RPC Device - %s", self.name)
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                await self.device.initialize()
        except OSError as err:
            raise update_coordinator.UpdateFailed("Device disconnected") from err

    @property
    def model(self) -> str:
        """Model of the device."""
        return cast(str, self.entry.data["model"])

    @property
    def mac(self) -> str:
        """Mac address of the device."""
        return cast(str, self.entry.unique_id)

    def async_setup(self) -> None:
        """Set up the wrapper."""
        dev_reg = device_registry.async_get(self.hass)
        sw_version = self.device.firmware_version if self.device.initialized else ""
        entry = dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            name=self.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.mac)},
            manufacturer="Shelly",
            model=aioshelly.const.MODEL_NAMES.get(self.model, self.model),
            sw_version=sw_version,
        )
        self.device_id = entry.id
        self.device.subscribe_updates(self.async_set_updated_data)

    async def shutdown(self) -> None:
        """Shutdown the wrapper."""
        await self.device.shutdown()

    async def _handle_ha_stop(self, _event: Event) -> None:
        """Handle Home Assistant stopping."""
        _LOGGER.debug("Stopping RpcDeviceWrapper for %s", self.name)
        await self.shutdown()
