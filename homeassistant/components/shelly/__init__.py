"""The Shelly integration."""
import asyncio
from datetime import timedelta
import logging

import aioshelly
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry, update_coordinator

from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    BATTERY_DEVICES_WITH_PERMANENT_CONNECTION,
    COAP,
    CONF_SLEEP_PERIOD,
    DATA_CONFIG_ENTRY,
    DEVICE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    INPUTS_EVENTS_DICT,
    POLLING_TIMEOUT_SEC,
    REST,
    REST_SENSORS_UPDATE_INTERVAL,
    SERVICE_OTA_UPDATE,
    SLEEP_PERIOD_MULTIPLIER,
    UPDATE_PERIOD_MULTIPLIER,
)
from .utils import get_coap_context, get_device_name, get_device_sleep_period

PLATFORMS = ["binary_sensor", "cover", "light", "sensor", "switch"]
SLEEPING_PLATFORMS = ["binary_sensor", "sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Shelly component."""
    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Shelly from a config entry."""
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = {}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = None

    temperature_unit = "C" if hass.config.units.is_metric else "F"

    options = aioshelly.ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        temperature_unit,
    )

    coap_context = await get_coap_context(hass)

    device = await aioshelly.Device.create(
        aiohttp_client.async_get_clientsession(hass),
        coap_context,
        options,
        False,
    )

    dev_reg = await device_registry.async_get_registry(hass)
    identifier = (DOMAIN, entry.unique_id)
    device_entry = dev_reg.async_get_device(identifiers={identifier}, connections=set())
    if device_entry and entry.entry_id not in device_entry.config_entries:
        device_entry = None

    sleep_period = entry.data.get(CONF_SLEEP_PERIOD)

    @callback
    def _async_device_online(_):
        _LOGGER.debug("Device %s is online, resuming setup", entry.title)
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = None

        if sleep_period is None:
            data = {**entry.data}
            data[CONF_SLEEP_PERIOD] = get_device_sleep_period(device.settings)
            data["model"] = device.settings["device"]["type"]
            hass.config_entries.async_update_entry(entry, data=data)

        hass.async_create_task(async_device_setup(hass, entry, device))

    if sleep_period == 0:
        # Not a sleeping device, finish setup
        _LOGGER.debug("Setting up online device %s", entry.title)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                await device.initialize(True)
        except (asyncio.TimeoutError, OSError) as err:
            raise ConfigEntryNotReady from err

        await async_device_setup(hass, entry, device)
    elif sleep_period is None or device_entry is None:
        # Need to get sleep info or first time sleeping device setup, wait for device
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = device
        _LOGGER.debug(
            "Setup for device %s will resume when device is online", entry.title
        )
        device.subscribe_updates(_async_device_online)
        await device.coap_request("s")
    else:
        # Restore sensors for sleeping device
        _LOGGER.debug("Setting up offline device %s", entry.title)
        await async_device_setup(hass, entry, device)

    await async_services_setup(hass, dev_reg)

    return True


async def async_device_setup(
    hass: HomeAssistant, entry: ConfigEntry, device: aioshelly.Device
):
    """Set up a device that is online."""
    device_wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        COAP
    ] = ShellyDeviceWrapper(hass, entry, device)
    await device_wrapper.async_setup()

    platforms = SLEEPING_PLATFORMS

    if not entry.data.get(CONF_SLEEP_PERIOD):
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
            REST
        ] = ShellyDeviceRestWrapper(hass, device)
        platforms = PLATFORMS

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )


async def async_services_setup(
    hass: HomeAssistant, dev_reg: device_registry.DeviceRegistry
):
    """Set up services."""

    async def async_service_ota_update(call: ServiceCall):
        """Trigger OTA update."""
        if not (call.data.get(ATTR_DEVICE_ID) or call.data.get(ATTR_AREA_ID)):
            _LOGGER.warning("OTA update service: no device or area selected")
            return

        devices = []
        if call.data.get(ATTR_AREA_ID):
            for area_id in call.data.get(ATTR_AREA_ID):
                devices += [
                    area_dev
                    for area_dev in device_registry.async_entries_for_area(
                        dev_reg, area_id
                    )
                    if DOMAIN in next(iter(area_dev.identifiers))
                ]

        if call.data.get(ATTR_DEVICE_ID):
            for device_id in call.data.get(ATTR_DEVICE_ID):
                device = dev_reg.async_get(device_id)
                if not any(device.id == x.id for x in devices):
                    devices += [device]

        for device in devices:
            entry_id = next(iter(device.config_entries))
            entry_data = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry_id]
            device_wrapper: ShellyDeviceWrapper = entry_data[COAP]
            if device_wrapper.is_ota_pending:
                _LOGGER.warning(
                    "There is already an ota update scheduled for device %s",
                    device.name,
                )
                continue

            await device_wrapper.async_trigger_ota_update(
                beta=call.data.get("beta"),
                url=call.data.get("url"),
                force=call.data.get("force"),
            )

    hass.services.async_register(DOMAIN, SERVICE_OTA_UPDATE, async_service_ota_update)


class ShellyDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass, entry, device: aioshelly.Device):
        """Initialize the Shelly device wrapper."""
        self.device_id = None
        sleep_period = entry.data[CONF_SLEEP_PERIOD]

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

        self._async_remove_device_updates_handler = self.async_add_listener(
            self._async_device_updates_handler
        )
        self._last_input_events_count = {}
        self._ota_update_pending = False
        self._ota_update_params = {}

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)

    @callback
    def _async_device_updates_handler(self):
        """Handle device updates."""
        if not self.device.initialized:
            return

        if self._ota_update_pending:
            self.async_trigger_ota_update()

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
        if self.entry.data.get(CONF_SLEEP_PERIOD):
            # Sleeping device, no point polling it, just mark it unavailable
            raise update_coordinator.UpdateFailed("Sleeping device did not update")

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

    @property
    def is_ota_pending(self):
        """Return if ota update is scheduled for device."""
        return self._ota_update_pending

    async def async_setup(self):
        """Set up the wrapper."""
        dev_reg = await device_registry.async_get_registry(self.hass)
        sw_version = self.device.settings["fw"] if self.device.initialized else ""
        entry = dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            name=self.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.mac)},
            # This is duplicate but otherwise via_device can't work
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Shelly",
            model=aioshelly.MODEL_NAMES.get(self.model, self.model),
            sw_version=sw_version,
        )
        self.device_id = entry.id
        self.device.subscribe_updates(self.async_set_updated_data)

    async def async_trigger_ota_update(self, beta=False, url=None, force=False):
        """Trigger an ota update."""
        if self.entry.data.get(CONF_SLEEP_PERIOD) and not self._ota_update_pending:
            self._ota_update_pending = True
            self._ota_update_params = {
                "beta": beta,
                "force": force,
                "url": url,
            }
            _LOGGER.info("OTA update scheduled for sleeping device %s", self.name)
            return

        def _reset_pending_ota():
            """Reset OTA update scheduler for sleeping device."""
            if self._ota_update_pending:
                _LOGGER.debug(
                    "Reset OTA update scheduler for sleeping device %s", self.name
                )
                self._ota_update_pending = False
                self._ota_update_params = {}

        if not self._ota_update_pending:
            await self.async_refresh()
        else:
            beta = self._ota_update_params["beta"]
            force = self._ota_update_params["force"]
            url = self._ota_update_params["url"]

        update_data = self.device.status["update"]
        _LOGGER.debug("OTA update service - update_data: %s", update_data)

        if not update_data["has_update"] and not beta and not url and not force:
            _LOGGER.info("No OTA update for %s available", self.name)
            _reset_pending_ota()
            return

        if beta and not update_data.get("beta_version"):
            _LOGGER.info("No beta OTA update for %s available", self.name)
            _reset_pending_ota()
            return

        if update_data["status"] == "updating":
            _LOGGER.warning("OTA update already in progress for %s", self.name)
            _reset_pending_ota()
            return

        new_version = update_data["new_version"]
        if beta:
            new_version = update_data["beta_version"]
        if url:
            new_version = url

        _LOGGER.info(
            "Trigger OTA update for device %s from '%s' to '%s'",
            self.name,
            update_data["old_version"],
            new_version,
        )

        resp = None
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                resp = await self.device.trigger_ota_update(
                    beta=beta,
                    url=url,
                )
        except OSError as err:
            _LOGGER.exception("Error while trigger ota update: %s", err)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Error while ota update: %s", err)

        _LOGGER.debug("OTA update response: %s", resp)
        _reset_pending_ota()
        return

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
    device = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id].get(DEVICE)
    if device is not None:
        # If device is present, device wrapper is not setup yet
        device.shutdown()
        return True

    platforms = SLEEPING_PLATFORMS

    if not entry.data.get(CONF_SLEEP_PERIOD):
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][REST] = None
        platforms = PLATFORMS

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in platforms
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][COAP].shutdown()
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

    return unload_ok
