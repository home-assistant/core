"""Switch entities for LocknAlert outputs/PGMs."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import LocknAlertConfigEntry
from .const import CONF_BRIDGE_SERIAL
from .entity import LocknAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LocknAlertConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    bridge_serial = str(entry.data[CONF_BRIDGE_SERIAL])

    @callback
    def _sync_entities() -> None:
        entities = [
            LocknAlertOutputSwitch(bridge_serial, output_id, output, coordinator.state.available)
            for output_id, output in coordinator.state.outputs.items()
        ]
        if entities:
            async_add_entities(entities)

    coordinator.async_listen("*", _sync_entities)
    _sync_entities()


class LocknAlertOutputSwitch(LocknAlertEntity, SwitchEntity):
    def __init__(self, bridge_id: str, output_id: str, output: dict, available: bool) -> None:
        super().__init__(bridge_id, f"output_{output_id}")
        self._output = output
        self._available = available
        self._attr_name = output.get("name", f"Output {output_id}")

    @property
    def is_on(self) -> bool:
        return bool(self._output.get("on", self._output.get("state") == "on"))
