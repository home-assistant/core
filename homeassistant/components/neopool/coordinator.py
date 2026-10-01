"""Data update coordinator for the NeoPool integration."""

import asyncio
from collections import defaultdict
from datetime import timedelta
import logging
from typing import Any, override

from neopool_modbus import NeoPoolModbusClient
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import (
    MAX_RELAY_GPIO,
    TIMER_BLOCKS,
    find_corrupted_gpio_registers,
    is_valid_relay_gpio,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_LIGHT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FOLLOW_UP_REFRESH_DELAY,
)

_LOGGER = logging.getLogger(__name__)

_FILT_TIMERS = ("filtration1", "filtration2", "filtration3")

# Config option gating each aux and light timer block.
_TIMER_OPTIONS: dict[str, str] = {
    "relay_aux1": CONF_USE_AUX1,
    "relay_aux1b": CONF_USE_AUX1,
    "relay_aux2": CONF_USE_AUX2,
    "relay_aux2b": CONF_USE_AUX2,
    "relay_aux3": CONF_USE_AUX3,
    "relay_aux3b": CONF_USE_AUX3,
    "relay_aux4": CONF_USE_AUX4,
    "relay_aux4b": CONF_USE_AUX4,
    "relay_light": CONF_USE_LIGHT,
}


type NeoPoolConfigEntry = ConfigEntry["NeoPoolCoordinator"]


class NeoPoolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for NeoPool platform."""

    client: NeoPoolModbusClient
    config_entry: NeoPoolConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: NeoPoolModbusClient,
        entry: NeoPoolConfigEntry,
    ) -> None:
        """Initialise the NeoPool data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self._corrupted_gpio_state: frozenset[tuple[str, int]] | None = None
        self._follow_up_unsub: CALLBACK_TYPE | None = None
        # Serializes masked read-modify-write across siblings sharing a register.
        self.masked_write_lock = asyncio.Lock()
        # One lock per timer block serializes the library's read-modify-write
        # across the block's start/stop sibling entities, which share a register.
        self._timer_write_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )

    def request_refresh_with_followup(
        self, delay: float = FOLLOW_UP_REFRESH_DELAY
    ) -> None:
        """Schedule a follow-up refresh after a delay.

        The follow-up catches delayed device state changes that may not
        be visible in Modbus registers immediately after a write.
        """
        self.cancel_follow_up_refresh()

        @callback
        def _do_refresh(_now: Any) -> None:
            self._follow_up_unsub = None
            self.hass.async_create_task(self.async_request_refresh())

        self._follow_up_unsub = async_call_later(self.hass, delay, _do_refresh)

    def cancel_follow_up_refresh(self) -> None:
        """Cancel any pending follow-up refresh."""
        if self._follow_up_unsub:
            self._follow_up_unsub()
            self._follow_up_unsub = None

    def timer_write_lock(self, block: str) -> asyncio.Lock:
        """Return the lock serializing sibling writes to one timer block."""
        return self._timer_write_locks[block]

    def _check_gpio_registers(self, data: dict[str, Any]) -> None:
        """Validate GPIO register values and (re-)raise or clear the repair issue."""
        corrupted = find_corrupted_gpio_registers(data)
        corrupted_state = frozenset((key, value) for key, _, value in corrupted)

        if corrupted_state == self._corrupted_gpio_state:
            return

        for key, label, value in corrupted:
            _LOGGER.error(
                "Corrupted GPIO register %s (%s): value %d (0x%04X) is outside "
                "valid range 0-%d. The pool controller may malfunction",
                key,
                label,
                value,
                value & 0xFFFF,
                MAX_RELAY_GPIO,
            )

        self._corrupted_gpio_state = corrupted_state

        if corrupted:
            details = "\n".join(
                f"- **{label}** (`{key}`): value **{value}** (expected 0-{MAX_RELAY_GPIO})"
                for key, label, value in corrupted
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "corrupted_gpio",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="corrupted_gpio",
                translation_placeholders={"details": details},
            )
        else:
            # Clear a previously raised repair issue once the device is healthy.
            ir.async_delete_issue(self.hass, DOMAIN, "corrupted_gpio")

    def _get_enabled_timers(self, data: dict[str, Any]) -> list[str]:
        """Return the timer block names to poll.

        Base aux and light blocks poll on their config option. The second aux
        subtimer and filtration blocks additionally require an active context
        (the block name registered by an enabled time entity).
        """
        options = self.config_entry.options
        active = {ctx for ctx in self.async_contexts() if isinstance(ctx, str)}
        enabled: list[str] = []
        for key in TIMER_BLOCKS:
            option_key = _TIMER_OPTIONS.get(key)
            if option_key is None:
                # Filtration timers gate on context below, not an option.
                continue
            if not options.get(option_key, False):
                continue
            # The b subtimer (time only) also needs an active context.
            if key.endswith("b") and key not in active:
                continue
            # Light GPIO invalid: the light entity gates the same, so
            # relay_light_enable has no consumer.
            if key == "relay_light" and not is_valid_relay_gpio(
                data.get("MBF_PAR_LIGHTING_GPIO", 0) or 0
            ):
                continue
            enabled.append(key)
        enabled += [ft for ft in _FILT_TIMERS if ft in active]
        return enabled

    async def _read_timers_into_data(self, data: dict[str, Any]) -> None:
        """Read every enabled timer block and merge derived fields into data.

        Exposes the enable flag (the light platform's manual-mode guard) and
        the start/stop endpoints consumed by the time platform. Further derived
        keys will be added by follow-up platform PRs that consume them.
        """
        enabled = self._get_enabled_timers(data)
        if not enabled:
            return
        timers = await self.client.read_all_timers(enabled_timers=enabled)
        for t_name, t in timers.items():
            data[f"{t_name}_enable"] = t["enable"]
            data[f"{t_name}_start"] = t["on"]  # seconds since midnight
            data[f"{t_name}_stop"] = t.get("stop")

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the pool controller."""
        try:
            data = await self.client.async_read_all()
            await self._read_timers_into_data(data)
        except (NeoPoolError, OSError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._check_gpio_registers(data)
        return data
