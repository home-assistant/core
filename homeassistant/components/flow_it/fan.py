"""Fan platform for Flow-it."""

from typing import Any, override

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.const import Speed
from flow_it_api.exceptions import FlowItAuthError, FlowItCommandError, FlowItError

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN
from .coordinator import FlowItConfigEntry, FlowItCoordinator
from .entity import FlowItVmcEntity

ORDERED_NAMED_FAN_SPEEDS = [
    Speed.LEVEL_1,
    Speed.LEVEL_2,
    Speed.LEVEL_3,
    Speed.LEVEL_4,
    Speed.LEVEL_5,
]

PRESET_MODES = [Speed.AUTO, Speed.BOOST]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlowItConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flow-it fan."""
    data = config_entry.runtime_data
    async_add_entities([FlowItVmcFan(data.coordinator, data.vmc)])


class FlowItVmcFan(FlowItVmcEntity, FanEntity):
    """Flow-it fan entity."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: FlowItCoordinator, vmc: FlowItVMCMachine) -> None:
        """Initialize the fan."""
        super().__init__(
            coordinator,
            vmc,
            FanEntityDescription(
                key="fan",
                name=None,
            ),
        )

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        return self.coordinator.data.state.data.mode.speed != Speed.OFF

    @override
    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        speed = self.coordinator.data.state.data.mode.speed
        if speed in ORDERED_NAMED_FAN_SPEEDS:
            return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, speed)
        return 0

    @override
    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @override
    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        speed = self.coordinator.data.state.data.mode.speed
        if speed in PRESET_MODES:
            return str(speed)
        return None

    @override
    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available preset modes."""
        return [str(s) for s in PRESET_MODES]

    async def _async_send_command(
        self, speed: Speed, flow_in: bool, flow_out: bool
    ) -> None:
        """Send a command to the VMC and handle exceptions."""
        try:
            await self.vmc.send_command(speed, flow_in=flow_in, flow_out=flow_out)
        except FlowItAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except FlowItCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except FlowItError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        await self.coordinator.async_refresh()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        mode = self.coordinator.data.state.data.mode
        await self._async_send_command(
            speed, flow_in=mode.flowIn, flow_out=mode.flowOut
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"Invalid preset mode: {preset_mode}")

        mode = self.coordinator.data.state.data.mode
        await self._async_send_command(
            Speed(preset_mode), flow_in=mode.flowIn, flow_out=mode.flowOut
        )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        mode = self.coordinator.data.state.data.mode
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            await self._async_send_command(
                Speed.LEVEL_1, flow_in=mode.flowIn, flow_out=mode.flowOut
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        mode = self.coordinator.data.state.data.mode
        await self._async_send_command(
            Speed.OFF, flow_in=mode.flowIn, flow_out=mode.flowOut
        )
