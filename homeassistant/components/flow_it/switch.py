"""Switch platform for Flow-it."""

from typing import Any, override

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.exceptions import FlowItAuthError, FlowItCommandError, FlowItError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FlowItConfigEntry, FlowItCoordinator
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
    async_add_entities(
        FlowItVmcFlowSwitch(data.coordinator, data.vmc, description)
        for description in SWITCHES
    )


class FlowItVmcFlowSwitch(FlowItVmcEntity, SwitchEntity):
    """Flow-it flow switch entity."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: FlowItCoordinator,
        vmc: FlowItVMCMachine,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, vmc, description)

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        mode = self.coordinator.data.state.data.mode
        if self.entity_description.key == "flow_in":
            return bool(mode.flowIn)  # codespell:ignore flowin
        return bool(mode.flowOut)

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
        mode = self.coordinator.data.state.data.mode
        speed = mode.speed
        if self.entity_description.key == "flow_in":
            flow_in = state
        else:
            flow_in = mode.flowIn  # codespell:ignore flowin
        flow_out = state if self.entity_description.key == "flow_out" else mode.flowOut

        try:
            await self.vmc.send_command(speed, flow_in=flow_in, flow_out=flow_out)
        except FlowItAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except (FlowItCommandError, FlowItError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err

        await self.coordinator.async_refresh()
