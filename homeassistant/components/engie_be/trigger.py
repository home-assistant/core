"""Automation triggers for the ENGIE Belgium integration."""

from abc import abstractmethod
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
from homeassistant.helpers.typing import UNDEFINED, ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
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
    DEVICE_IDS_SCHEMA,
    THRESHOLD_SCHEMA,
    async_get_device_epex,
    async_validate_epex_options,
    price_in_range,
    validate_threshold,
)


class _EpexTrigger(Trigger):
    """Base for triggers that watch the EPEX prices of ENGIE Belgium devices.

    Each update of the EPEX coordinator, including the quarter-hour tick,
    computes a value per device and compares it against the previous one.
    """

    _options_schema: probatio.Schema = probatio.Schema(DEVICE_IDS_SCHEMA)

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
    def _value(self, data: EngieBeEpexData, now: datetime) -> Any:
        """Return the value to compare between two updates."""

    @abstractmethod
    def _fires(self, previous: Any, current: Any) -> bool:
        """Return True when the change from previous to current fires."""

    def _device_value(self, device_id: str) -> Any:
        """Return the value for one device, or UNDEFINED when it is not known."""
        epex = async_get_device_epex(self._hass, device_id)
        if epex is None or not epex.last_update_success:
            return UNDEFINED
        return self._value(epex.data, dt_util.utcnow())

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
        description = f"EPEX prices changed for {device.name_by_user or device.name}"
        tracked_coordinator = async_get_device_epex(self._hass, device_id)
        previous: Any = self._device_value(device_id)

        @callback
        def async_epex_updated(coordinator: EngieBeEpexCoordinator) -> None:
            """Compare the device value against the previous update."""
            nonlocal previous, tracked_coordinator
            if coordinator is not tracked_coordinator:
                tracked_coordinator = coordinator
                previous = UNDEFINED

            current = self._device_value(device_id)
            if (
                previous is not UNDEFINED
                and current is not UNDEFINED
                and self._fires(previous, current)
            ):
                run_action({ATTR_DEVICE_ID: device_id}, description)
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


class _EpexBecameTrueTrigger(_EpexTrigger):
    """Base for triggers that fire when a check goes from false to true."""

    @override
    def _fires(self, previous: bool | None, current: bool | None) -> bool:
        """Return True on the change from false to true."""
        return previous is False and current is True


class _EpexNegativeTrigger(_EpexBecameTrueTrigger):
    """Base for triggers on the sign of the current EPEX price."""

    _granularity: EpexGranularity
    _negative: bool

    @override
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool | None:
        """Return whether the current price has the watched sign."""
        negative = epex_is_negative(data, self._granularity, now)
        return None if negative is None else negative is self._negative


class EpexHourBecameNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the hourly EPEX price becomes negative."""

    _granularity = EpexGranularity.HOURLY
    _negative = True


class EpexHourNoLongerNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the hourly EPEX price is no longer negative."""

    _granularity = EpexGranularity.HOURLY
    _negative = False


class EpexQuarterHourBecameNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the quarter-hourly EPEX price becomes negative."""

    _granularity = EpexGranularity.QUARTER_HOURLY
    _negative = True


class EpexQuarterHourNoLongerNegativeTrigger(_EpexNegativeTrigger):
    """Trigger that fires when the quarter-hourly EPEX price is no longer negative."""

    _granularity = EpexGranularity.QUARTER_HOURLY
    _negative = False


class EpexTomorrowPricesPublishedTrigger(_EpexBecameTrueTrigger):
    """Trigger that fires when the EPEX prices of tomorrow become available."""

    @override
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool:
        """Return whether both granularities cover tomorrow."""
        return epex_day_available(data, epex_tomorrow(now))


class _EpexCrossedThresholdTrigger(_EpexBecameTrueTrigger):
    """Base for triggers that fire when an EPEX price enters a range."""

    _options_schema = probatio.Schema(
        probatio.All({**DEVICE_IDS_SCHEMA, **THRESHOLD_SCHEMA}, validate_threshold)
    )
    _granularity: EpexGranularity
    _next: bool

    @override
    def _value(self, data: EngieBeEpexData, now: datetime) -> bool | None:
        """Return whether the watched price is inside the range."""
        price = (epex_next_price if self._next else epex_price_at)(
            data, self._granularity, now
        )
        if price is None:
            return None
        return price_in_range(
            price, self._options.get(CONF_ABOVE), self._options.get(CONF_BELOW)
        )


class EpexCurrentHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the current hourly EPEX price crosses a threshold."""

    _granularity = EpexGranularity.HOURLY
    _next = False


class EpexNextHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the next hourly EPEX price crosses a threshold."""

    _granularity = EpexGranularity.HOURLY
    _next = True


class EpexCurrentQuarterHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the current quarter-hourly EPEX price crosses a threshold."""

    _granularity = EpexGranularity.QUARTER_HOURLY
    _next = False


class EpexNextQuarterHourCrossedThresholdTrigger(_EpexCrossedThresholdTrigger):
    """Trigger that fires when the next quarter-hourly EPEX price crosses a threshold."""

    _granularity = EpexGranularity.QUARTER_HOURLY
    _next = True


TRIGGERS: dict[str, type[Trigger]] = {
    "epex_current_hour_crossed_threshold": EpexCurrentHourCrossedThresholdTrigger,
    "epex_current_quarter_hour_crossed_threshold": (
        EpexCurrentQuarterHourCrossedThresholdTrigger
    ),
    "epex_hour_became_negative": EpexHourBecameNegativeTrigger,
    "epex_hour_no_longer_negative": EpexHourNoLongerNegativeTrigger,
    "epex_next_hour_crossed_threshold": EpexNextHourCrossedThresholdTrigger,
    "epex_next_quarter_hour_crossed_threshold": (
        EpexNextQuarterHourCrossedThresholdTrigger
    ),
    "epex_quarter_hour_became_negative": EpexQuarterHourBecameNegativeTrigger,
    "epex_quarter_hour_no_longer_negative": EpexQuarterHourNoLongerNegativeTrigger,
    "epex_tomorrow_prices_published": EpexTomorrowPricesPublishedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for the ENGIE Belgium integration."""
    return TRIGGERS
