"""Base entities for Broadlink Magic Home."""

import time
from typing import Any, override

from broadlink_magic import ImportedDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, family_identifier
from .coordinator import FamilyCoordinator

PENDING_COMMAND_TIMEOUT = 30.0


class PendingCommands:
    """Commanded values waiting for a confirming device report."""

    def __init__(self) -> None:
        """Initialize an empty set of pending commands."""
        self._values: dict[str, tuple[int, int, float]] = {}

    def set(self, key: str, value: int, serial: int) -> None:
        """Record a value commanded after the device report with this serial."""
        self._values[key] = (
            value,
            serial,
            time.monotonic() + PENDING_COMMAND_TIMEOUT,
        )

    def discard(self, key: str) -> None:
        """Forget a commanded value."""
        self._values.pop(key, None)

    def confirmed(self, reported: dict[str, Any], serial: int) -> dict[str, Any]:
        """Return reported values that do not contradict pending commands.

        A periodic report sent before a command took effect still carries the
        old value, so a pending key is only cleared by a newer report of the
        device that confirms it, or once the confirmation window has passed.
        """
        now = time.monotonic()
        state: dict[str, Any] = {}
        for key, value in reported.items():
            if (pending := self._values.get(key)) is not None:
                expected, sent_serial, deadline = pending
                matches = int(value) == expected
                if now >= deadline or (matches and serial > sent_serial):
                    del self._values[key]
                elif not matches:
                    continue
            state[key] = value
        return state


class BroadLinkMagicEntity(CoordinatorEntity[FamilyCoordinator]):
    """Base class for entities of an imported Magic Home family."""

    _attr_has_entity_name = True

    def _family_device_id(self) -> str:
        """Return the registry id of the imported family device."""
        return dr.async_get_device_id_by_identifier(
            self.coordinator.hass,
            (DOMAIN, family_identifier(self.coordinator.family.family_id)),
            config_entry_id=self.coordinator.config_entry.entry_id,
        )

    def _report_serial(self, device: ImportedDevice) -> int:
        """Return the number of reports received from a device."""
        return self.coordinator.report_serials.get(device.stable_id, 0)

    def _confirmed_state(
        self, device: ImportedDevice, pending: PendingCommands
    ) -> dict[str, Any]:
        """Return the reported state of a device filtered by pending commands."""
        return pending.confirmed(
            self.coordinator.device_states.get(device.stable_id, {}),
            self._report_serial(device),
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether at least one family gateway is online."""
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.gateway_set.online_gateways
        )
