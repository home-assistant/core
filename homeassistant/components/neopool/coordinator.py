"""Data update coordinator for the NeoPool integration."""

from datetime import timedelta
import logging
from typing import Any, override

from neopool_modbus import NeoPoolModbusClient
from neopool_modbus.decoders import aggregate_filtration_remaining, parse_version
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import GPIO_REGISTERS, MAX_RELAY_GPIO

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import CONF_FILTRATION_PUMP_POWER, DEFAULT_SCAN_INTERVAL, DOMAIN

MAX_SCAN_INTERVAL = timedelta(seconds=180)

_FILT_TIMERS = ("filtration1", "filtration2", "filtration3")

_LOGGER = logging.getLogger(__name__)


class NeoPoolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for NeoPool platform."""

    client: NeoPoolModbusClient

    def __init__(
        self,
        hass: HomeAssistant,
        client: NeoPoolModbusClient,
        entry: ConfigEntry,
        entry_id: str,
    ) -> None:
        """Initialise the NeoPool data update coordinator."""
        self.normal_update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        self.max_update_interval = min(
            self.normal_update_interval * 4, MAX_SCAN_INTERVAL
        )
        self._consecutive_errors = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=self.normal_update_interval,
            config_entry=entry,
        )
        self.client = client
        self.entry = entry
        self.entry_id = entry_id
        self.device_name = entry.title or DOMAIN
        self._firmware = "?"
        self._model = "Unknown"
        self._gpio_checked = False

    def _check_gpio_registers(self, data: dict) -> None:
        """Validate GPIO register values after first successful read."""
        corrupted = []
        for key, label in GPIO_REGISTERS.items():
            value = data.get(key)
            if value is not None and not (0 <= value <= MAX_RELAY_GPIO):
                corrupted.append((key, label, value))
                _LOGGER.error(
                    "Corrupted GPIO register %s (%s): value %d (0x%04X) is outside "
                    "valid range 0-%d. The pool controller may malfunction",
                    key,
                    label,
                    value,
                    value & 0xFFFF,
                    MAX_RELAY_GPIO,
                )

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
            # Clear previous repair issues if registers are OK.
            ir.async_delete_issue(self.hass, DOMAIN, "corrupted_gpio")
            _LOGGER.info("GPIO registers passed sanity check: all values are valid")

    async def _read_timers_into_data(self, data: dict[str, Any]) -> None:
        """Read every enabled timer block and merge derived fields into data."""
        prev_remaining = self.data.get("FILTRATION_REMAINING") if self.data else None
        filtration_active = bool(data.get("Filtration Pump")) or bool(
            prev_remaining and prev_remaining > 0
        )
        timers = await self.client.read_all_timers(
            enabled_timers=list(_FILT_TIMERS),
            force_read=_FILT_TIMERS if filtration_active else None,
        )
        for t_name, t in timers.items():
            data[f"{t_name}_enable"] = t["enable"]
            data[f"{t_name}_start"] = t["on"]  # seconds since midnight
            data[f"{t_name}_interval"] = t["interval"]
            data[f"{t_name}_period"] = t["period"]
            data[f"{t_name}_countdown"] = t["countdown"]
            data[f"{t_name}_stop"] = t.get("stop")

        data["FILTRATION_REMAINING"] = aggregate_filtration_remaining(data)

    async def _handle_modbus_failure(self, err: Exception) -> None:
        """Increment the error counter and slow down polling exponentially."""
        self._consecutive_errors += 1
        _LOGGER.error("Modbus communication error: %s (%s)", err, type(err).__name__)
        current_interval = self.update_interval or self.normal_update_interval
        next_interval = min(current_interval * 2, self.max_update_interval)
        if self.update_interval != next_interval:
            _LOGGER.warning(
                "Increasing update interval to %s seconds due to communication errors",
                int(next_interval.total_seconds()),
            )
            self.update_interval = next_interval
        _LOGGER.warning("Modbus error - marking all entities unavailable")

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the pool controller."""
        try:
            data = await self.client.async_read_all()
        except (NeoPoolError, OSError, TimeoutError) as err:
            await self._handle_modbus_failure(err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._consecutive_errors = 0

        if self.update_interval != self.normal_update_interval:  # pragma: no cover
            _LOGGER.info(
                "Communication OK, resetting update interval to %s seconds",
                self.normal_update_interval.total_seconds(),
            )
            self.update_interval = self.normal_update_interval

        self._firmware = parse_version(data.get("MBF_POWER_MODULE_VERSION"))
        self._model = "NeoPool"

        if not self._gpio_checked:
            self._gpio_checked = True
            self._check_gpio_registers(data)

        await self._read_timers_into_data(data)

        pump_power = max(
            0, int(self.entry.options.get(CONF_FILTRATION_PUMP_POWER, 0) or 0)
        )
        data[CONF_FILTRATION_PUMP_POWER] = (
            pump_power if data.get("Filtration Pump") else 0
        )

        return data

    @property
    def firmware(self) -> str:
        """Return the device firmware version string."""
        return self._firmware

    @property
    def model(self) -> str:
        """Return the device model string."""
        return self._model

    @property
    def device_slug(self) -> str:  # pragma: no cover
        """Return the slugified device name used as object_id prefix."""
        return slugify(self.device_name)
