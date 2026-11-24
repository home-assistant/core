"""BenQ Projector Infrared integration for Home Assistant."""

from datetime import datetime, timedelta

from homeassistant.components.infrared import async_get_emitters, async_get_receivers
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COOL_DOWN_TIME,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_WARM_UP_TIME,
    DEFAULT_COOL_DOWN_TIME,
    DEFAULT_WARM_UP_TIME,
    DOMAIN,
    POWER_OFF_CONFIRM_WINDOW,
    BenQProjectorBusyReason,
)

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]


class BenQProjectorIrRuntimeData:
    """Runtime data for a BenQ projector config entry.

    The projector ignores every command while it warms up or cools down, and only
    powers off when a second off press confirms the first. Both are tracked at the
    device level so all entities of a config entry share them.
    """

    def __init__(self, *, warm_up_time: timedelta, cool_down_time: timedelta) -> None:
        """Initialize the runtime data."""
        self._warm_up_time = warm_up_time
        self._cool_down_time = cool_down_time
        self._busy_until: datetime | None = None
        self._busy_reason = BenQProjectorBusyReason.WARMING_UP
        self._power_off_requested_at: datetime | None = None

    def start_warm_up(self) -> None:
        """Start the warm-up after the projector is turned on."""
        self._start(BenQProjectorBusyReason.WARMING_UP, self._warm_up_time)

    def start_cool_down(self) -> None:
        """Start the cool-down after the projector is turned off."""
        self._start(BenQProjectorBusyReason.COOLING_DOWN, self._cool_down_time)

    def _start(self, reason: BenQProjectorBusyReason, duration: timedelta) -> None:
        self._busy_reason = reason
        self._busy_until = dt_util.utcnow() + duration

    @property
    def busy_reason(self) -> BenQProjectorBusyReason:
        """Return why the projector ignores commands, while it is busy."""
        return self._busy_reason

    def request_power_off(self) -> bool:
        """Register a power-off press and return whether it confirms an earlier one.

        The first press only shows the confirmation prompt on the projector.
        """
        now = dt_util.utcnow()
        requested_at = self._power_off_requested_at
        if requested_at is not None and now - requested_at <= POWER_OFF_CONFIRM_WINDOW:
            self._power_off_requested_at = None
            return True
        self._power_off_requested_at = now
        return False

    def dismiss_power_off(self) -> None:
        """Dismiss a pending power-off confirmation, as any other key does."""
        self._power_off_requested_at = None

    def busy_remaining(self) -> timedelta | None:
        """Return how long the projector still ignores commands, if it does."""
        if self._busy_until is None:
            return None
        if (remaining := self._busy_until - dt_util.utcnow()) > timedelta(0):
            return remaining
        self._busy_until = None
        return None


type BenQProjectorIrConfigEntry = ConfigEntry[BenQProjectorIrRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: BenQProjectorIrConfigEntry
) -> None:
    """Set up BenQ Projector Infrared from a config entry."""
    entity_registry = er.async_get(hass)
    emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    if entity_registry.async_get(
        emitter_entity_id
    ) is None and emitter_entity_id not in async_get_emitters(hass):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="emitter_not_found"
        )
    if (
        (receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID))
        and entity_registry.async_get(receiver_entity_id) is None
        and receiver_entity_id not in async_get_receivers(hass)
    ):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="receiver_not_found"
        )
    entry.runtime_data = BenQProjectorIrRuntimeData(
        warm_up_time=timedelta(
            seconds=entry.options.get(CONF_WARM_UP_TIME, DEFAULT_WARM_UP_TIME)
        ),
        cool_down_time=timedelta(
            seconds=entry.options.get(CONF_COOL_DOWN_TIME, DEFAULT_COOL_DOWN_TIME)
        ),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: BenQProjectorIrConfigEntry
) -> None:
    """Unload a BenQ Projector Infrared config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
