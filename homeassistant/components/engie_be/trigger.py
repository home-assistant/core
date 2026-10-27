"""Automation triggers for the ENGIE Belgium integration."""

from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, override

from aioengiebelgium import EpexGranularity
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_ABOVE, CONF_BELOW
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.util import dt as dt_util

from .const import ATTR_PRICE, DOMAIN
from .coordinator import (
    SIGNAL_EPEX_UPDATED,
    EngieBeEpexCoordinator,
    EngieBeEpexData,
    epex_day_available,
    epex_is_negative,
    epex_next_price,
    epex_price_at,
    epex_tomorrow,
)
from .helpers import (
    DEVICE_IDS_OPTIONS_SCHEMA,
    THRESHOLD_OPTIONS_SCHEMA,
    async_get_device_epex,
    async_get_device_epex_data,
    async_validate_epex_options,
    price_in_range,
)


class _EpexTrigger(Trigger):
    """Base for triggers that watch the EPEX prices of ENGIE Belgium devices.

    Each update of the EPEX coordinator, including the quarter-hour tick,
    computes a check per device and fires when it goes from false to true.
    """

    _options_schema: probatio.Schema = DEVICE_IDS_OPTIONS_SCHEMA
    _event: str

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return async_validate_epex_options(hass, config, cls._options_schema)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._options: dict[str, Any] = config.options
        self._device_ids: list[str] = config.options[ATTR_DEVICE_ID]

    @abstractmethod
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool | None:
        """Return the check to compare between two updates."""

    def _device_value(self, device_id: str) -> bool | UndefinedType | None:
        """Return the check for one device, or UNDEFINED when it is not known."""
        data = async_get_device_epex_data(self._hass, device_id)
        if data is None:
            return UNDEFINED
        return self._value(data, dt_util.utcnow())

    def _price(self, data: EngieBeEpexData, now: datetime) -> float | None:
        """Return the price to add to the trigger data, or None to leave it out."""
        return None

    def _trigger_data(self, device_id: str) -> dict[str, Any]:
        """Return the trigger data passed to the automation."""
        trigger_data: dict[str, Any] = {ATTR_DEVICE_ID: device_id}
        data = async_get_device_epex_data(self._hass, device_id)
        if (
            data is not None
            and (price := self._price(data, dt_util.utcnow())) is not None
        ):
            trigger_data[ATTR_PRICE] = price
        return trigger_data

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        unsubscribes: list[CALLBACK_TYPE] = []
        for device_id in self._device_ids:
            device, entry = dr.async_get_device_and_config_entry_for_domain(
                self._hass, device_id, domain=DOMAIN
            )
            if device is None or entry is None:
                continue
            unsubscribes.append(
                self._async_track_device(device_id, device, entry, run_action)
            )

        @callback
        def async_remove() -> None:
            """Stop tracking the devices."""
            for unsubscribe in unsubscribes:
                unsubscribe()

        return async_remove

    @callback
    def _async_track_device(
        self,
        device_id: str,
        device: dr.AnyDeviceEntry,
        entry: ConfigEntry,
        run_action: TriggerActionRunner,
    ) -> CALLBACK_TYPE:
        """Track the EPEX prices for a single device."""
        description = f"{self._event} for {device.name_by_user or device.name}"
        tracked_coordinator = async_get_device_epex(self._hass, device_id)
        previous: bool | UndefinedType | None = self._device_value(device_id)

        @callback
        def async_epex_updated(coordinator: EngieBeEpexCoordinator) -> None:
            """Compare the device value against the previous update."""
            nonlocal previous, tracked_coordinator
            if coordinator is not tracked_coordinator:
                tracked_coordinator = coordinator
                previous = UNDEFINED

            current = self._device_value(device_id)
            if previous is False and current is True:
                run_action(self._trigger_data(device_id), description)
            previous = current

        @callback
        def async_entry_state_changed() -> None:
            """Take the first comparison value once a reloaded entry is loaded.

            The first update of a new coordinator arrives before the entry
            is loaded, so it can not provide a value to compare against.
            """
            nonlocal previous
            if entry.state is ConfigEntryState.LOADED and previous is UNDEFINED:
                previous = self._device_value(device_id)

        remove_dispatcher = async_dispatcher_connect(
            self._hass, SIGNAL_EPEX_UPDATED.format(entry.entry_id), async_epex_updated
        )
        remove_state_listener = entry.async_on_state_change(async_entry_state_changed)

        @callback
        def async_remove() -> None:
            """Stop tracking the device."""
            remove_dispatcher()
            remove_state_listener()

        return async_remove


class _EpexNegativeTrigger(_EpexTrigger):
    """Base for triggers on the sign of the current EPEX price."""

    _granularity: EpexGranularity
    _negative: bool

    @override
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool | None:
        """Return whether the current price has the watched sign."""
        negative = epex_is_negative(data, self._granularity, now)
        return None if negative is None else negative is self._negative

    @override
    def _price(self, data: EngieBeEpexData, now: datetime) -> float | None:
        """Return the current price."""
        return epex_price_at(data, self._granularity, now)


class EpexHourBecameNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the hourly EPEX price becomes negative."""

    _event = "hourly EPEX price became negative"
    _granularity = EpexGranularity.HOURLY
    _negative = True


class EpexHourNoLongerNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the hourly EPEX price is no longer negative."""

    _event = "hourly EPEX price no longer negative"
    _granularity = EpexGranularity.HOURLY
    _negative = False


class EpexQuarterHourBecameNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the quarter-hourly EPEX price becomes negative."""

    _event = "quarter-hourly EPEX price became negative"
    _granularity = EpexGranularity.QUARTER_HOURLY
    _negative = True


class EpexQuarterHourNoLongerNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the quarter-hourly EPEX price is no longer negative."""

    _event = "quarter-hourly EPEX price no longer negative"
    _granularity = EpexGranularity.QUARTER_HOURLY
    _negative = False


class EpexTomorrowPricesPublishedTrigger(_EpexTrigger):
    """Trigger that fires when the EPEX prices of tomorrow become available."""

    _event = "EPEX prices for tomorrow published"

    @override
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool:
        """Return whether both granularities cover tomorrow."""
        return epex_day_available(data, epex_tomorrow(now))


class _EpexCrossedThresholdTrigger(_EpexTrigger):
    """Base for triggers that fire when an EPEX price enters a range."""

    _options_schema = THRESHOLD_OPTIONS_SCHEMA
    _granularity: EpexGranularity
    _price_fn: Callable[[EngieBeEpexData, EpexGranularity, datetime], float | None]

    @override
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool | None:
        """Return whether the watched price is inside the range."""
        price = self._price_fn(data, self._granularity, now)
        if price is None:
            return None
        return price_in_range(
            price, self._options.get(CONF_ABOVE), self._options.get(CONF_BELOW)
        )

    @override
    def _price(self, data: EngieBeEpexData, now: datetime) -> float | None:
        """Return the watched price."""
        return self._price_fn(data, self._granularity, now)


class EpexCurrentHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the current hourly EPEX price crosses a threshold."""

    _event = "current hourly EPEX price crossed threshold"
    _granularity = EpexGranularity.HOURLY
    _price_fn = staticmethod(epex_price_at)


class EpexNextHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the next hourly EPEX price crosses a threshold."""

    _event = "next hourly EPEX price crossed threshold"
    _granularity = EpexGranularity.HOURLY
    _price_fn = staticmethod(epex_next_price)


class EpexCurrentQuarterHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the current quarter-hourly EPEX price crosses a threshold."""

    _event = "current quarter-hourly EPEX price crossed threshold"
    _granularity = EpexGranularity.QUARTER_HOURLY
    _price_fn = staticmethod(epex_price_at)


class EpexNextQuarterHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the next quarter-hourly EPEX price crosses a threshold."""

    _event = "next quarter-hourly EPEX price crossed threshold"
    _granularity = EpexGranularity.QUARTER_HOURLY
    _price_fn = staticmethod(epex_next_price)


TRIGGERS: dict[str, type[Trigger]] = {
    "epex_current_hour_crossed_threshold": EpexCurrentHourCrossedThresholdTrigger,
    "epex_current_quarter_hour_crossed_threshold": (
        EpexCurrentQuarterHourCrossedThresholdTrigger
    ),
    "epex_hour_price_became_negative": EpexHourBecameNegativeTrigger,
    "epex_hour_price_no_longer_negative": EpexHourNoLongerNegativeTrigger,
    "epex_next_hour_crossed_threshold": EpexNextHourCrossedThresholdTrigger,
    "epex_next_quarter_hour_crossed_threshold": (
        EpexNextQuarterHourCrossedThresholdTrigger
    ),
    "epex_quarter_hour_price_became_negative": EpexQuarterHourBecameNegativeTrigger,
    "epex_quarter_hour_price_no_longer_negative": EpexQuarterHourNoLongerNegativeTrigger,
    "epex_tomorrow_prices_published": EpexTomorrowPricesPublishedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for the ENGIE Belgium integration."""
    return TRIGGERS
