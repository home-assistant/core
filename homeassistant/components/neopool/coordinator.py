"""Data update coordinator for the NeoPool integration."""

from datetime import timedelta
import logging
from typing import Any, override

from neopool_modbus import NeoPoolModbusClient
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import (
    MAX_RELAY_GPIO,
    find_corrupted_gpio_registers,
    is_valid_relay_gpio,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CAPABILITY_KEYS,
    CONF_CAPABILITIES,
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

# Auxiliary relay timer blocks keyed by their enabling option.
_AUX_TIMER_BLOCKS: dict[str, str] = {
    CONF_USE_AUX1: "relay_aux1",
    CONF_USE_AUX2: "relay_aux2",
    CONF_USE_AUX3: "relay_aux3",
    CONF_USE_AUX4: "relay_aux4",
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
        # Winter mode maps onto the native per-entry "disable polling" system
        # option; the base coordinator already skips scheduling when it's set.
        self.winter_mode = entry.pref_disable_polling
        # Persisted in options for winter mode (no Modbus reads).
        self._capability_snapshot: dict[str, Any] = dict(
            entry.options.get(CONF_CAPABILITIES, {})
        )
        self._corrupted_gpio_state: frozenset[tuple[str, int]] | None = None
        self._follow_up_unsub: CALLBACK_TYPE | None = None

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
        """Return the list of timer block names to poll each cycle.

        The light timer is polled only when its option is enabled and the
        lighting GPIO is valid. Auxiliary relay timers are polled per enabled
        option; the aux switches read relay_aux*_enable as a manual-mode guard.
        """
        enabled: list[str] = []
        if self.config_entry.options.get(CONF_USE_LIGHT, False) and is_valid_relay_gpio(
            data.get("MBF_PAR_LIGHTING_GPIO", 0) or 0
        ):
            enabled.append("relay_light")
        enabled.extend(
            block
            for option, block in _AUX_TIMER_BLOCKS.items()
            if self.config_entry.options.get(option, False)
        )
        return enabled

    async def _read_timers_into_data(self, data: dict[str, Any]) -> None:
        """Read every enabled timer block and merge derived fields into data.

        Only the ``<timer>_enable`` field is exposed: it is the sole timer
        attribute consumed by the light platform (as a manual-mode guard).
        Further derived keys will be added by follow-up platform PRs that
        consume them.
        """
        enabled = self._get_enabled_timers(data)
        if not enabled:
            return
        timers = await self.client.read_all_timers(enabled_timers=enabled)
        for t_name, t in timers.items():
            data[f"{t_name}_enable"] = t["enable"]

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the pool controller."""
        if self.winter_mode:
            _LOGGER.debug("Winter mode active - skipping Modbus communication")
            return self.data if self.data is not None else self._capability_snapshot

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
        self._persist_capability_snapshot(data)
        return data

    def _persist_capability_snapshot(self, data: dict[str, Any]) -> None:
        """Persist the capability snapshot so platform setup survives HA restarts."""
        new_snapshot = {k: data[k] for k in CAPABILITY_KEYS if k in data}
        if new_snapshot == self._capability_snapshot:
            return
        self._capability_snapshot = new_snapshot
        options = dict(self.config_entry.options)
        options[CONF_CAPABILITIES] = new_snapshot
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    async def set_winter_mode(self, enabled: bool) -> None:
        """Toggle winter mode via the native disable-polling flag.

        Winter mode is backed by ``config_entry.pref_disable_polling`` so the
        base coordinator stops scheduling refreshes entirely (no no-op polls,
        no reconnect attempts). When enabling, the capability snapshot is
        persisted first so the reload can set entities up offline, then the
        entry is reloaded to rebuild the coordinator with the new flag.
        """
        self.winter_mode = enabled
        updates: dict[str, Any] = {"pref_disable_polling": enabled}
        if enabled and self.data:
            self._capability_snapshot = {
                k: self.data[k] for k in CAPABILITY_KEYS if k in self.data
            }
            options = dict(self.config_entry.options)
            options[CONF_CAPABILITIES] = dict(self._capability_snapshot)
            updates["options"] = options
        self.hass.config_entries.async_update_entry(self.config_entry, **updates)
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
