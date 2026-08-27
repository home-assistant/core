"""DataUpdateCoordinator for the optional local Modbus data source."""

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from bluetti_modbus_lib.base_devices import BluettiDevice
from bluetti_modbus_lib.modbus.client import ClientReturnValue
from modbus_connection.exceptions import (
    AcknowledgeError,
    ModbusError,
    ServerDeviceBusyError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import BluettiConfigEntry

_LOGGER = logging.getLogger(__name__)

# Matches the cloud coordinator's cadence. Bluetti's Modbus TCP stack is
# known to become unresponsive under connection/poll pressure - a rapid
# burst of connections during testing once required a factory reset to
# recover - so there is no reason to poll faster locally just because it's
# local.
UPDATE_INTERVAL = timedelta(seconds=30)


class BluettiModbusCoordinator(DataUpdateCoordinator[dict[str, ClientReturnValue]]):
    """Coordinate polling of one device's optional local Modbus connection.

    Unlike bluetti_modbus_lib.modbus.client.BluettiModbusClient (which owns
    its own Modbus connection - fine for a standalone HACS install, but not
    for Home Assistant Core, where the shared connection obtained via
    homeassistant.components.modbus.async_get_unit() must be reused, not
    duplicated), this coordinator is handed an already-connected device
    object and only knows how to poll it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BluettiConfigEntry,
        device_id: str,
        device: BluettiDevice,
    ) -> None:
        """Initialize the coordinator for a single device's Modbus connection."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"bluetti-modbus-{device_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> dict[str, ClientReturnValue]:
        """Fetch the latest field values over Modbus."""
        try:
            await self._update_with_timeout()
        except (AcknowledgeError, ServerDeviceBusyError):
            # Codes 5/6: the device accepted the request but wants more time,
            # or is momentarily busy - both are explicitly meant to be
            # retried, not treated as a hard failure. Retry exactly once.
            _LOGGER.debug("Device asked for a retry, trying once more")
            try:
                await self._update_with_timeout()
            except ModbusError as err:
                raise self._update_failed(err) from err
        except ModbusError as err:
            raise self._update_failed(err) from err

        results: dict[str, ClientReturnValue] = {}
        # bluetti_modbus_lib doesn't expose a public accessor for the fields
        # that came back on the last read yet - tracked as a follow-up to
        # request one upstream.
        for name, value in self.device._values.items():  # noqa: SLF001
            field = self.device.get_field(name)
            assert field is not None, f"{name} is in _values, so it must be a registered field"
            results[name] = ClientReturnValue(name=name, unit=field.unit, value=value)
        return results

    def _update_failed(self, err: ModbusError) -> UpdateFailed:
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="modbus_error",
            translation_placeholders={"error": str(err)},
        )

    async def _update_with_timeout(self) -> None:
        # One async_update() call reads several register blocks sequentially
        # (see modbus_connection's ReadPlan.execute), so this timeout must
        # budget the whole sequence, not one request. A real production bug
        # (see bluetti-modbus PR #26) traced recurring "Request cancelled
        # outside library" errors to this same value being too tight for
        # that - a single slow block (this device's Modbus TCP stack is
        # known to become unresponsive under load) could consume nearly the
        # whole budget, cancelling whichever block came next. 30s matches
        # UPDATE_INTERVAL: an update that takes longer than a full poll
        # cycle should fail and retry next cycle regardless.
        async with asyncio.timeout(30):
            await self.device.async_update()
