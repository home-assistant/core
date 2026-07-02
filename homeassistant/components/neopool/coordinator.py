"""Data update coordinator for the NeoPool integration."""

from datetime import timedelta
import logging
from typing import Any, override

from neopool_modbus import NeoPoolModbusClient
from neopool_modbus.decoders import parse_version
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import MAX_RELAY_GPIO, find_corrupted_gpio_registers

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NeoPoolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for NeoPool platform."""

    client: NeoPoolModbusClient
    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: NeoPoolModbusClient,
        entry: ConfigEntry,
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
        self._firmware = "?"
        self._corrupted_gpio_keys: frozenset[str] = frozenset()

    def _check_gpio_registers(self, data: dict) -> None:
        """Validate GPIO register values and (re-)raise or clear the repair issue."""
        corrupted = find_corrupted_gpio_registers(data)
        corrupted_keys = frozenset(key for key, _, _ in corrupted)

        if corrupted_keys != self._corrupted_gpio_keys:
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

        self._corrupted_gpio_keys = corrupted_keys

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

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the pool controller."""
        try:
            data = await self.client.async_read_all()
        except (NeoPoolError, OSError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._firmware = parse_version(data.get("MBF_POWER_MODULE_VERSION"))
        self._check_gpio_registers(data)

        return data

    @property
    def firmware(self) -> str:
        """Return the device firmware version string."""
        return self._firmware
