"""The Shelly integration."""
import asyncio
from datetime import timedelta
import logging
from socket import gethostbyname

import aioshelly
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry, update_coordinator

from .config_flow import HTTP_CONNECT_ERRORS, validate_input
from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    BATTERY_DEVICES_WITH_PERMANENT_CONNECTION,
    COAP,
    DATA_CONFIG_ENTRY,
    DATA_SENSORS,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    INPUTS_EVENTS_DICT,
    POLLING_TIMEOUT_SEC,
    REST,
    REST_SENSORS_UPDATE_INTERVAL,
    SLEEP_PERIOD_MULTIPLIER,
    UPDATE_PERIOD_MULTIPLIER,
)
from .utils import get_coap_context, get_device_name

PLATFORMS = ["binary_sensor", "cover", "light", "sensor", "switch"]
SLEEPING_PLATFORMS = ["binary_sensor", "sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Shelly component."""
    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}, DATA_SENSORS: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Shelly from a config entry."""
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = {}
    device = None

    temperature_unit = "C" if hass.config.units.is_metric else "F"

    ip_address = await hass.async_add_executor_job(gethostbyname, entry.data[CONF_HOST])

    options = aioshelly.ConnectionOptions(
        ip_address,
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        temperature_unit,
    )

    coap_context = await get_coap_context(hass)

    # First check if device is not sleeping
    try:
        async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
            device = await aioshelly.Device.create(
                aiohttp_client.async_get_clientsession(hass),
                coap_context,
                options,
                True,
            )
    except (asyncio.TimeoutError, OSError) as err:
        # Not a sleepign device, raise error
        if not entry.data["sleep_period"]:
            raise ConfigEntryNotReady from err

    # Sleeping device, make an empty device
    if device is None:
        async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
            device = await aioshelly.Device.create(
                aiohttp_client.async_get_clientsession(hass),
                coap_context,
                options,
                False,
            )

    coap_wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        COAP
    ] = ShellyDeviceWrapper(hass, entry, device)
    await coap_wrapper.async_setup()

    # All ready, perform full setup
    if device.initialized:
        _LOGGER.debug("Device ready - IP:%s", ip_address)
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
            REST
        ] = ShellyDeviceRestWrapper(hass, device)

        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )
        return True

    _LOGGER.debug("Device not ready - IP:%s", ip_address)

    # Setup only sensors for sleeping device
    for component in SLEEPING_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate the config entry upon new versions."""
    version = entry.version
    data = {**entry.data}

    _LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Add sleep_period
    if version == 1:
        try:
            device_info = await validate_input(
                hass,
                entry.data[CONF_HOST],
                {
                    CONF_USERNAME: entry.data.get(CONF_USERNAME),
                    CONF_PASSWORD: entry.data.get(CONF_PASSWORD),
                },
            )
        except HTTP_CONNECT_ERRORS:
            return False

        data["sleep_period"] = device_info["sleep_period"]
        data["model"] = device_info["model"]
        version = entry.version = 2
        hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.debug("Migration to version %s successful", version)

    return True


class ShellyDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass, entry, device: aioshelly.Device):
        """Initialize the Shelly device wrapper."""
        self.device_id = None
        self.restored_device = False
        self.restored_entities = []
        self.sensors = None
        sleep_period = entry.data["sleep_period"]

        if sleep_period:
            update_interval = SLEEP_PERIOD_MULTIPLIER * sleep_period
        else:
            update_interval = (
                UPDATE_PERIOD_MULTIPLIER * device.settings["coiot"]["update_period"]
            )

        device_name = get_device_name(device) if device.initialized else entry.title
        super().__init__(
            hass,
            _LOGGER,
            name=device_name,
            update_interval=timedelta(seconds=update_interval),
        )
        self.hass = hass
        self.entry = entry
        self.device = device

        self.device.subscribe_updates(self.async_set_updated_data)

        self._async_remove_device_updates_handler = self.async_add_listener(
            self._async_device_updates_handler
        )
        self._last_input_events_count = dict()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)

    @callback
    def _async_device_updates_handler(self):
        """Handle device updates."""
        if not self.device.initialized:
            return

        # Restored device initialized, update entities
        if self.restored_device:
            _LOGGER.debug("Restoring Shelly Device - %s", self.name)
            for block in self.device.blocks:
                for sensor_id in block.sensor_ids:
                    description = self.hass.data[DOMAIN][DATA_SENSORS]["sensor"].get(
                        (block.type, sensor_id)
                    ) or self.hass.data[DOMAIN][DATA_SENSORS]["binary_sensor"].get(
                        (block.type, sensor_id)
                    )
                    if description is None:
                        continue

                    # Filter out non-existing sensors and sensors without a value
                    if getattr(block, sensor_id, None) in (-1, None):
                        continue

                    unique_id = f"{self.mac}-{block.description}-{sensor_id}"

                    for entity in self.restored_entities:
                        if entity.unique_id == unique_id:
                            entity.set_block_attribute_description(
                                sensor_id, block, description
                            )

            self.restored_device = False

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
                    },
                )
            else:
                _LOGGER.warning(
                    "Shelly input event %s for device %s is not supported, please open issue",
                    event_type,
                    self.name,
                )

    async def _async_update_data(self):
        """Fetch data."""
        _LOGGER.debug("Polling Shelly Device - %s", self.name)
        try:
            async with async_timeout.timeout(POLLING_TIMEOUT_SEC):
                return await self.device.update()
        except OSError as err:
            raise update_coordinator.UpdateFailed("Error fetching data") from err

    @property
    def model(self):
        """Model of the device."""
        return self.entry.data["model"]

    @property
    def mac(self):
        """Mac address of the device."""
        return self.entry.unique_id

    async def async_setup(self):
        """Set up the wrapper."""
        dev_reg = await device_registry.async_get_registry(self.hass)

        if self.device.initialized:
            model_type = self.device.settings["device"]["type"]
            entry = dev_reg.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                name=self.name,
                connections={(device_registry.CONNECTION_NETWORK_MAC, self.mac)},
                # This is duplicate but otherwise via_device can't work
                identifiers={(DOMAIN, self.mac)},
                manufacturer="Shelly",
                model=aioshelly.MODEL_NAMES.get(model_type, model_type),
                sw_version=self.device.settings["fw"],
            )
            self.device_id = entry.id
        else:
            identifier = (DOMAIN, self.entry.unique_id)
            device_entry = dev_reg.async_get_device(
                identifiers={identifier}, connections=set()
            )
            self.device_id = device_entry.id
            self.restored_device = True

    def shutdown(self):
        """Shutdown the wrapper."""
        self.device.shutdown()
        self._async_remove_device_updates_handler()

    @callback
    def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        _LOGGER.debug("Stopping ShellyDeviceWrapper for %s", self.name)
        self.shutdown()


class ShellyDeviceRestWrapper(update_coordinator.DataUpdateCoordinator):
    """Rest Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass, device: aioshelly.Device):
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
            name=get_device_name(device),
            update_interval=timedelta(seconds=update_interval),
        )
        self.device = device

    async def _async_update_data(self):
        """Fetch data."""
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                _LOGGER.debug("REST update for %s", self.name)
                return await self.device.update_status()
        except OSError as err:
            raise update_coordinator.UpdateFailed("Error fetching data") from err

    @property
    def mac(self):
        """Mac address of the device."""
        return self.device.settings["device"]["mac"]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][COAP].shutdown()
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

    return unload_ok
