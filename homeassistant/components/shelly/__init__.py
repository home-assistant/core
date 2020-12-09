"""The Shelly integration."""
import asyncio
from datetime import timedelta
import logging
from socket import gethostbyname

import aioshelly
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    device_registry,
    singleton,
    update_coordinator,
)

from .const import (
    COAP,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    INPUTS_EVENTS_DICT,
    POLLING_TIMEOUT_MULTIPLIER,
    REST,
    REST_SENSORS_UPDATE_INTERVAL,
    SETUP_ENTRY_TIMEOUT_SEC,
    SLEEP_PERIOD_MULTIPLIER,
    UPDATE_PERIOD_MULTIPLIER,
)
from .utils import get_device_name

PLATFORMS = ["binary_sensor", "cover", "light", "sensor", "switch"]
_LOGGER = logging.getLogger(__name__)


@singleton.singleton("shelly_coap")
async def get_coap_context(hass):
    """Get CoAP context to be used in all Shelly devices."""
    context = aioshelly.COAP()
    await context.initialize()

    @callback
    def shutdown_listener(ev):
        context.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_listener)

    return context


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Shelly component."""
    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Shelly from a config entry."""
    temperature_unit = "C" if hass.config.units.is_metric else "F"

    ip_address = await hass.async_add_executor_job(gethostbyname, entry.data[CONF_HOST])

    options = aioshelly.ConnectionOptions(
        ip_address,
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        temperature_unit,
    )

    coap_context = await get_coap_context(hass)

    try:
        async with async_timeout.timeout(SETUP_ENTRY_TIMEOUT_SEC):
            device = await aioshelly.Device.create(
                aiohttp_client.async_get_clientsession(hass),
                coap_context,
                options,
            )
    except (asyncio.TimeoutError, OSError) as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = {}
    coap_wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        COAP
    ] = ShellyDeviceWrapper(hass, entry, device)
    await coap_wrapper.async_setup()

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        REST
    ] = ShellyDeviceRestWrapper(hass, device)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class ShellyDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass, entry, device: aioshelly.Device):
        """Initialize the Shelly device wrapper."""
        self.device_id = None
        sleep_mode = device.settings.get("sleep_mode")

        if sleep_mode:
            sleep_period = sleep_mode["period"]
            if sleep_mode["unit"] == "h":
                sleep_period *= 60  # hours to minutes

            update_interval = (
                SLEEP_PERIOD_MULTIPLIER * sleep_period * 60
            )  # minutes to seconds
        else:
            update_interval = (
                UPDATE_PERIOD_MULTIPLIER * device.settings["coiot"]["update_period"]
            )

        super().__init__(
            hass,
            _LOGGER,
            name=get_device_name(device),
            update_interval=timedelta(seconds=update_interval),
        )
        self.hass = hass
        self.entry = entry
        self.device = device

        self.device.subscribe_updates(self.async_set_updated_data)

        self._async_remove_input_events_handler = self.async_add_listener(
            self._async_input_events_handler
        )
        self._last_input_events_count = dict()

    @callback
    def _async_input_events_handler(self):
        """Handle device input events."""
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
                    "shelly.click",
                    {
                        "device_id": self.device_id,
                        "device": self.device.settings["device"]["hostname"],
                        "channel": channel,
                        "click_type": INPUTS_EVENTS_DICT[event_type],
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
            async with async_timeout.timeout(
                POLLING_TIMEOUT_MULTIPLIER
                * self.device.settings["coiot"]["update_period"]
            ):
                return await self.device.update()
        except OSError as err:
            raise update_coordinator.UpdateFailed("Error fetching data") from err

    @property
    def model(self):
        """Model of the device."""
        return self.device.settings["device"]["type"]

    @property
    def mac(self):
        """Mac address of the device."""
        return self.device.settings["device"]["mac"]

    async def async_setup(self):
        """Set up the wrapper."""
        dev_reg = await device_registry.async_get_registry(self.hass)
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

    def shutdown(self):
        """Shutdown the wrapper."""
        self.device.shutdown()
        self._async_remove_input_events_handler()


class ShellyDeviceRestWrapper(update_coordinator.DataUpdateCoordinator):
    """Rest Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass, device: aioshelly.Device):
        """Initialize the Shelly device wrapper."""

        super().__init__(
            hass,
            _LOGGER,
            name=get_device_name(device),
            update_interval=timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL),
        )
        self.device = device

    async def _async_update_data(self):
        """Fetch data."""
        try:
            async with async_timeout.timeout(5):
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
