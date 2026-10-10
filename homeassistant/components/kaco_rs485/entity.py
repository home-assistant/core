"""Shared entity base: one device per inverter."""

from typing import override

from kaco_rs485 import InverterState

from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INVERTERS, CONF_SW_VERSION, DOMAIN, MANUFACTURER, SERIES_PREFIX
from .coordinator import KacoRs485Coordinator


def _device_name(address: int, inverter_type: str | None) -> str:
    """e.g. `"KACO Powador 6400xi (1)"`.

    The address is always part of the name: it is the only identifier these
    units expose, and it is set in the inverter's own display menu.
    """
    if not inverter_type:
        return f"Inverter {address}"
    return f"{SERIES_PREFIX} {inverter_type} ({address})"


class KacoRs485Entity(CoordinatorEntity[KacoRs485Coordinator]):
    """Base for every entity belonging to one inverter."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KacoRs485Coordinator, address: int) -> None:
        """Initialize the entity for one inverter address."""
        super().__init__(coordinator)
        self._address = address

        entry = coordinator.config_entry
        # From the entry, not the poll: at night there is nothing to read.
        recorded = entry.data[CONF_INVERTERS].get(str(address), {})
        model = recorded.get(CONF_MODEL)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{address}")},
            name=_device_name(address, model),
            manufacturer=MANUFACTURER,
            model=model,
            # No serial_number: xi units answer command `s` with zero bytes.
            sw_version=recorded.get(CONF_SW_VERSION) or None,
        )

    @property
    def inverter(self) -> InverterState | None:
        """Return this inverter's latest state, if it has one."""
        return self.coordinator.data.get(self._address)

    @property
    @override
    def available(self) -> bool:
        """Unavailable once the inverter has stopped answering.

        Follows the library's backoff threshold, not just the coordinator's: a
        dark inverter must not keep showing yesterday's watts at midnight.
        """
        state = self.inverter
        return super().available and state is not None and state.available
