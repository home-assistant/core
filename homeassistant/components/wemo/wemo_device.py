"""Home Assistant wrapper for a pyWeMo device."""
import asyncio
from datetime import timedelta
import logging

from pywemo import Insight, LongPressMixin, WeMoDevice
from pywemo.exceptions import ActionException
from pywemo.subscribe import EVENT_TYPE_LONG_PRESS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PARAMS,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_UPNP,
    async_get as async_get_device_registry,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, WEMO_SUBSCRIPTION_EVENT

_LOGGER = logging.getLogger(__name__)


class DeviceCoordinator(DataUpdateCoordinator):
    """Home Assistant wrapper for a pyWeMo device."""

    def __init__(self, hass: HomeAssistant, wemo: WeMoDevice, device_id: str) -> None:
        """Initialize DeviceCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=wemo.name,
            update_interval=timedelta(seconds=30),
        )
        self.hass = hass
        self.wemo = wemo
        self.device_id = device_id
        self.device_info = _device_info(wemo)
        self.supports_long_press = wemo.supports_long_press()
        self.update_lock = asyncio.Lock()

    def subscription_callback(
        self, _device: WeMoDevice, event_type: str, params: str
    ) -> None:
        """Receives push notifications from WeMo devices."""
        _LOGGER.debug("Subscription event (%s) for %s", event_type, self.wemo.name)
        if event_type == EVENT_TYPE_LONG_PRESS:
            self.hass.bus.fire(
                WEMO_SUBSCRIPTION_EVENT,
                {
                    CONF_DEVICE_ID: self.device_id,
                    CONF_NAME: self.wemo.name,
                    CONF_TYPE: event_type,
                    CONF_PARAMS: params,
                    CONF_UNIQUE_ID: self.wemo.serialnumber,
                },
            )
        else:
            updated = self.wemo.subscription_update(event_type, params)
            self.hass.create_task(self._async_subscription_callback(updated))

    async def _async_subscription_callback(self, updated: bool) -> None:
        """Update the state by the Wemo device."""
        # If an update is in progress, we don't do anything.
        if self.update_lock.locked():
            return
        try:
            await self._async_locked_update(not updated)
        except UpdateFailed as err:
            self.last_exception = err
            if self.last_update_success:
                _LOGGER.exception("Subscription callback failed")
                self.last_update_success = False
        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.last_update_success = False
            _LOGGER.exception("Unexpected error fetching %s data: %s", self.name, err)
        else:
            self.async_set_updated_data(None)

    @property
    def should_poll(self) -> bool:
        """Return True if polling is needed to update the state for the device.

        The alternative, when this returns False, is to rely on the subscription
        "push updates" to update the device state in Home Assistant.
        """
        if isinstance(self.wemo, Insight) and self.wemo.get_state() == 0:
            # The WeMo Insight device does not send subscription updates for the
            # insight_params values when the device is off. Polling is required in
            # this case so the Sensor entities are properly populated.
            return True

        registry = self.hass.data[DOMAIN]["registry"]
        return not (registry.is_subscribed(self.wemo) and self.last_update_success)

    async def _async_update_data(self) -> None:
        """Update WeMo state."""
        # No need to poll if the device will push updates.
        if not self.should_poll:
            return

        # If an update is in progress, we don't do anything.
        if self.update_lock.locked():
            return

        await self._async_locked_update(True)

    async def _async_locked_update(self, force_update: bool) -> None:
        """Try updating within an async lock."""
        async with self.update_lock:
            try:
                await self.hass.async_add_executor_job(
                    self.wemo.get_state, force_update
                )
            except ActionException as err:
                raise UpdateFailed("WeMo update failed") from err


def _device_info(wemo: WeMoDevice) -> DeviceInfo:
    return DeviceInfo(
        connections={(CONNECTION_UPNP, wemo.udn)},
        identifiers={(DOMAIN, wemo.serialnumber)},
        manufacturer="Belkin",
        model=wemo.model_name,
        name=wemo.name,
        sw_version=wemo.firmware_version,
    )


async def async_register_device(
    hass: HomeAssistant, config_entry: ConfigEntry, wemo: WeMoDevice
) -> DeviceCoordinator:
    """Register a device with home assistant and enable pywemo event callbacks."""
    # Ensure proper communication with the device and get the initial state.
    await hass.async_add_executor_job(wemo.get_state, True)

    device_registry = async_get_device_registry(hass)
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, **_device_info(wemo)
    )

    device = DeviceCoordinator(hass, wemo, entry.id)
    hass.data[DOMAIN].setdefault("devices", {})[entry.id] = device
    registry = hass.data[DOMAIN]["registry"]
    registry.on(wemo, None, device.subscription_callback)
    await hass.async_add_executor_job(registry.register, wemo)

    if isinstance(wemo, LongPressMixin):
        try:
            await hass.async_add_executor_job(wemo.ensure_long_press_virtual_device)
        # Temporarily handling all exceptions for #52996 & pywemo/pywemo/issues/276
        # Replace this with `except: PyWeMoException` after upstream has been fixed.
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Failed to enable long press support for device: %s", wemo.name
            )
            device.supports_long_press = False

    return device


@callback
def async_get_coordinator(hass: HomeAssistant, device_id: str) -> DeviceCoordinator:
    """Return DeviceCoordinator for device_id."""
    coordinator: DeviceCoordinator = hass.data[DOMAIN]["devices"][device_id]
    return coordinator
