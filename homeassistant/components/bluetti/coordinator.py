"""DataUpdateCoordinators for the BLUETTI integration's cloud and optional local Modbus sources."""

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from bluetti_modbus_lib.base_devices import BluettiDevice as ModbusDevice
from bluetti_modbus_lib.modbus.client import ClientReturnValue
from modbus_connection.exceptions import (
    AcknowledgeError,
    ModbusError,
    ServerDeviceBusyError,
)
from pybluetti import ApplicationRuntimeException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import BluettiDevice

if TYPE_CHECKING:
    # Deliberately not a runtime import: __init__.py imports this module to
    # define BluettiConfigEntry in the first place, so importing it back
    # here would be circular. TYPE_CHECKING avoids that while still giving
    # mypy the precise type (matches the same pattern models.py already
    # uses for BluettiDeviceCoordinator).
    from . import BluettiConfigEntry

_LOGGER = logging.getLogger(__name__)

# Also matches BluettiModbusCoordinator's cadence below. Bluetti's Modbus TCP
# stack is known to become unresponsive under connection/poll pressure - a
# rapid burst of connections during testing once required a factory reset to
# recover - so there is no reason to poll faster locally just because it's
# local.
UPDATE_INTERVAL = timedelta(seconds=30)

# msgCode values that mean the OAuth token is no longer valid.
AUTH_ERROR_CODES = {401, 805}


class BluettiDeviceCoordinator(DataUpdateCoordinator[BluettiDevice]):
    """Coordinate REST polling and websocket-triggered refreshes for one device."""

    def __init__(
        self, hass: HomeAssistant, entry: BluettiConfigEntry, device: BluettiDevice
    ) -> None:
        """Initialize the coordinator for a single BLUETTI device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"bluetti-{device.device_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        device.coordinator = self

    @override
    async def _async_update_data(self) -> BluettiDevice:
        """Fetch the latest state for the device from the BLUETTI cloud API."""
        try:
            await self.device.async_refresh_from_api()
        except ApplicationRuntimeException as err:
            if err.msgCode in AUTH_ERROR_CODES:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_expired",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return self.device


# One async_update() call reads several register blocks sequentially (see
# modbus_connection's ReadPlan.execute), so this timeout must budget the
# whole sequence, not one request. A real production bug (see bluetti-modbus
# PR #26) traced recurring "Request cancelled outside library" errors to
# this same value being too tight for that - a single slow block (this
# device's Modbus TCP stack is known to become unresponsive under load)
# could consume nearly the whole budget, cancelling whichever block came
# next. 30s matches UPDATE_INTERVAL: an update that takes longer than a
# full poll cycle should fail and retry next cycle regardless. A module
# constant, not an inline literal, so tests can shrink it instead of
# actually sleeping through a real 30s budget.
UPDATE_TIMEOUT = timedelta(seconds=30)


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
        device: ModbusDevice,
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

    @override
    async def _async_update_data(self) -> dict[str, ClientReturnValue]:
        """Fetch the latest field values over Modbus."""
        try:
            await self._update_with_timeout()
        except AcknowledgeError, ServerDeviceBusyError:
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
        # self.device.values is the fields that came back on the last
        # successful read (as opposed to field_names()/declared_fields/
        # resolved_fields, which are the STATIC schema - what the device
        # type CAN report, not what it actually read this cycle). Added
        # upstream in bluetti-modbus 0.1.2 - see
        # https://github.com/bluetti-community/bluetti-modbus/issues/27 and
        # PR #28 - specifically so this integration doesn't need to reach
        # into the private Component._values dict it's built from.
        for name, value in self.device.values.items():
            field = self.device.get_field(name)
            assert field is not None, (
                f"{name} is in values, so it must be a registered field"
            )
            results[name] = ClientReturnValue(name=name, unit=field.unit, value=value)
        return results

    def _update_failed(self, err: ModbusError) -> UpdateFailed:
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="modbus_error",
            translation_placeholders={"error": str(err)},
        )

    async def _update_with_timeout(self) -> None:
        async with asyncio.timeout(UPDATE_TIMEOUT.total_seconds()):
            await self.device.async_update()
