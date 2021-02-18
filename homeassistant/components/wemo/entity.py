"""Classes shared among Wemo entities."""
import asyncio
import contextlib
import logging
from typing import Any, Dict, Generator, Optional

import async_timeout
from pywemo import WeMoDevice
from pywemo.ouimeaux_device.api.service import ActionException

from homeassistant.helpers.entity import Entity

from .const import DOMAIN as WEMO_DOMAIN

_LOGGER = logging.getLogger(__name__)


class ExceptionHandlerStatus:
    """Exit status from the _wemo_exception_handler context manager."""

    # An exception if one was raised in the _wemo_exception_handler.
    exception: Optional[Exception] = None

    @property
    def success(self) -> bool:
        """Return True if the handler completed with no exception."""
        return self.exception is None


class WemoEntity(Entity):
    """Common methods for Wemo entities.

    Requires that subclasses implement the _update method.
    """

    def __init__(self, device: WeMoDevice) -> None:
        """Initialize the WeMo device."""
        self.wemo = device
        self._state = None
        self._available = True
        self._update_lock = None

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.wemo.name

    @property
    def available(self) -> bool:
        """Return true if switch is available."""
        return self._available

    @contextlib.contextmanager
    def _wemo_exception_handler(
        self, message: str
    ) -> Generator[ExceptionHandlerStatus, None, None]:
        """Wrap device calls to set `_available` when wemo exceptions happen."""
        status = ExceptionHandlerStatus()
        try:
            yield status
        except ActionException as err:
            status.exception = err
            _LOGGER.warning("Could not %s for %s (%s)", message, self.name, err)
            self._available = False
        else:
            if not self._available:
                _LOGGER.info("Reconnected to %s", self.name)
                self._available = True

    def _update(self, force_update: Optional[bool] = True):
        """Update the device state."""
        raise NotImplementedError()

    async def async_added_to_hass(self) -> None:
        """Wemo device added to Home Assistant."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

    async def async_update(self) -> None:
        """Update WeMo state.

        Wemo has an aggressive retry logic that sometimes can take over a
        minute to return. If we don't get a state within the scan interval,
        assume the Wemo switch is unreachable. If update goes through, it will
        be made available again.
        """
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        try:
            async with async_timeout.timeout(
                self.platform.scan_interval.seconds - 0.1
            ) as timeout:
                await asyncio.shield(self._async_locked_update(True, timeout))
        except asyncio.TimeoutError:
            _LOGGER.warning("Lost connection to %s", self.name)
            self._available = False

    async def _async_locked_update(
        self, force_update: bool, timeout: Optional[async_timeout.timeout] = None
    ) -> None:
        """Try updating within an async lock."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(self._update, force_update)
            # When the timeout expires HomeAssistant is no longer waiting for an
            # update from the device. Instead, the state needs to be updated
            # asynchronously. This also handles the case where an update came
            # directly from the device (device push). In that case no polling
            # update was involved and the state also needs to be updated
            # asynchronously.
            if not timeout or timeout.expired:
                self.async_write_ha_state()


class WemoSubscriptionEntity(WemoEntity):
    """Common methods for Wemo devices that register for update callbacks."""

    @property
    def unique_id(self) -> str:
        """Return the id of this WeMo device."""
        return self.wemo.serialnumber

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device info."""
        return {
            "name": self.name,
            "identifiers": {(WEMO_DOMAIN, self.unique_id)},
            "model": self.wemo.model_name,
            "manufacturer": "Belkin",
        }

    @property
    def is_on(self) -> bool:
        """Return true if the state is on. Standby is on."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """Wemo device added to Home Assistant."""
        await super().async_added_to_hass()

        registry = self.hass.data[WEMO_DOMAIN]["registry"]
        await self.hass.async_add_executor_job(registry.register, self.wemo)
        registry.on(self.wemo, None, self._subscription_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Wemo device removed from hass."""
        registry = self.hass.data[WEMO_DOMAIN]["registry"]
        await self.hass.async_add_executor_job(registry.unregister, self.wemo)

    def _subscription_callback(
        self, _device: WeMoDevice, _type: str, _params: str
    ) -> None:
        """Update the state by the Wemo device."""
        _LOGGER.info("Subscription update for %s", self.name)
        updated = self.wemo.subscription_update(_type, _params)
        self.hass.add_job(self._async_locked_subscription_callback(not updated))

    async def _async_locked_subscription_callback(self, force_update: bool) -> None:
        """Handle an update from a subscription."""
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        await self._async_locked_update(force_update)
