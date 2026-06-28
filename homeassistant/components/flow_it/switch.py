"""Switch platform for Flow-it."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlowItConfigEntry
from .entity import FlowItVmcEntity

SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="flow_in",
        translation_key="flow_in",
    ),
    SwitchEntityDescription(
        key="flow_out",
        translation_key="flow_out",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlowItConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flow-it switches."""
    data = config_entry.runtime_data
    coordinator = data.coordinator
    vmc = data.vmc

    async_add_entities(
        FlowItVmcFlowSwitch(coordinator, vmc, description) for description in SWITCHES
    )


class FlowItVmcFlowSwitch(FlowItVmcEntity, SwitchEntity):
    """Flow-it flow switch entity."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: Any,
        vmc: Any,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, vmc)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.name}_{description.key}"

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.entity_description.key == "flow_in":
            return bool(self.coordinator.data.data.mode.flowIn)
        return bool(self.coordinator.data.data.mode.flowOut)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_flow(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_flow(False)

    async def _async_set_flow(self, state: bool) -> None:
        """Set the flow state."""
        mode = self.coordinator.data.data.mode
        speed = mode.speed
        flow_in = state if self.entity_description.key == "flow_in" else mode.flowIn
        flow_out = state if self.entity_description.key == "flow_out" else mode.flowOut

        await self.vmc.send_command(speed, flow_in=flow_in, flow_out=flow_out)
        await self.coordinator.async_refresh()
