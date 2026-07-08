"""Data update coordinator for the NeoPool integration."""

from datetime import timedelta
import logging
from typing import Any, override

from neopool_modbus import NeoPoolModbusClient
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import MAX_RELAY_GPIO, find_corrupted_gpio_registers

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_USE_LIGHT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FOLLOW_UP_REFRESH_DELAY,
)

_FILT_TIMERS = ("filtration1", "filtration2", "filtration3")

_LOGGER = logging.getLogger(__name__)


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

    def request_refresh_with_followup(
        self, delay: float = FOLLOW_UP_REFRESH_DELAY
    ) -> None:
        """Schedule a follow-up refresh after a delay.

        The follow-up catches delayed device state changes that may not
        be visible in Modbus registers immediately after a write.
        """
        if self._follow_up_unsub:
            self._follow_up_unsub()
            self._follow_up_unsub = None

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

    def _get_enabled_timers(self) -> list[str]:
        """Return the list of timer block names to poll each cycle.

        Filtration timers are polled unconditionally because they feed the
        aggregate filtration state; the light timer is polled only when the
        light entity is enabled in the options.
        """
        enabled: list[str] = list(_FILT_TIMERS)
        if self.config_entry.options.get(CONF_USE_LIGHT, False):
            enabled.append("relay_light")
        return enabled

    async def _read_timers_into_data(self, data: dict[str, Any]) -> None:
        """Read every enabled timer block and merge derived fields into data."""
        prev_remaining = self.data.get("FILTRATION_REMAINING") if self.data else None
        filtration_active = bool(data.get("Filtration Pump")) or bool(
            prev_remaining and prev_remaining > 0
        )
        timers = await self.client.read_all_timers(
            enabled_timers=self._get_enabled_timers(),
            force_read=_FILT_TIMERS if filtration_active else None,
        )
        for t_name, t in timers.items():
            data[f"{t_name}_enable"] = t["enable"]
            data[f"{t_name}_start"] = t["on"]  # seconds since midnight
            data[f"{t_name}_interval"] = t["interval"]
            data[f"{t_name}_period"] = t["period"]
            data[f"{t_name}_countdown"] = t["countdown"]
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
