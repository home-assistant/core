"""Classes shared among Wemo entities."""
from __future__ import annotations

from collections.abc import Generator
import contextlib
import logging

from pywemo.exceptions import ActionException

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as WEMO_DOMAIN, SIGNAL_WEMO_STATE_PUSH
from .wemo_device import DeviceWrapper

_LOGGER = logging.getLogger(__name__)


class WemoEntity(CoordinatorEntity):
    """Common methods for Wemo entities."""

    # Most pyWeMo devices are associated with a single Home Assistant entity. When
    # that is not the case, name_suffix & unique_id_suffix can be used to provide
    # names and unique ids for additional Home Assistant entities.
    _name_suffix: str | None = None
    _unique_id_suffix: str | None = None

    @property
    def success(self) -> bool:
        """Return True if the handler completed with no exception."""
        return self.exception is None


class WemoEntity(Entity):
    """Common methods for Wemo entities.

    Requires that subclasses implement the _update method.
    """

    def __init__(self, wemo: WeMoDevice) -> None:
        """Initialize the WeMo device."""
        self.wemo = wemo
        self._state = None
        self._available = True

    @property
    def name_suffix(self):
        """Suffix to append to the WeMo device name."""
        return self._name_suffix

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        suffix = self.name_suffix
        if suffix:
            return f"{self.wemo.name} {suffix}"
        return self.wemo.name

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        return super().available and self._available

    @property
    def unique_id_suffix(self):
        """Suffix to append to the WeMo device's unique ID."""
        if self._unique_id_suffix is None and self.name_suffix is not None:
            return self._name_suffix.lower()
        return self._unique_id_suffix

    def __init__(self, device: DeviceWrapper) -> None:
        """Initialize WemoSubscriptionEntity."""
        super().__init__(device.wemo)
        self._device_id = device.device_id
        self._device_info = device.device_info

    @property
    def unique_id(self) -> str:
        """Return the id of this WeMo device."""
        suffix = self.unique_id_suffix
        if suffix:
            return f"{self.wemo.serialnumber}_{suffix}"
        return self.wemo.serialnumber

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._available = True
        super()._handle_coordinator_update()

    @property
    def should_poll(self) -> bool:
        """Return True if the the device requires local polling, False otherwise.

        It is desirable to allow devices to enter periods of polling when the
        callback subscription (device push) is not working. To work with the
        entity platform polling logic, this entity needs to report True for
        should_poll initially. That is required to cause the entity platform
        logic to start the polling task (see the discussion in #47182).

        Polling can be disabled if three conditions are met:
        1. The device has polled to get the initial state (self._has_polled) and
           to satisfy the entity platform constraint mentioned above.
        2. The polling was successful and the device is in a healthy state
           (self.available).
        3. The pywemo subscription registry reports that there is an active
           subscription and the subscription has been confirmed by receiving an
           initial event. This confirms that device push notifications are
           working correctly (registry.is_subscribed - this method is async safe).
        """
        registry = self.hass.data[WEMO_DOMAIN]["registry"]
        return not (
            self.available and self._has_polled and registry.is_subscribed(self.wemo)
        )

    async def async_added_to_hass(self) -> None:
        """Wemo device added to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_WEMO_STATE_PUSH, self._async_subscription_callback
            )
        )

    async def _async_subscription_callback(
        self, device_id: str, event_type: str, params: str
    ) -> None:
        """Update the state by the Wemo device."""
        # Only respond events for this device.
        if device_id != self._device_id:
            return
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        _LOGGER.debug("Subscription event (%s) for %s", event_type, self.name)
        updated = await self.hass.async_add_executor_job(
            self.wemo.subscription_update, event_type, params
        )
        await self._async_locked_update(not updated)
