"""Switches for the settings of an Intesis gateway and its air conditioner."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, override

from intesis_gw_modbus import IntesisSingleUnitGateway

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntesisConfigEntry, IntesisCoordinator, IntesisUnitCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class IntesisSwitchEntityDescription(SwitchEntityDescription):
    """A setting that is on or off, and where to read and write it."""

    report_name: str
    value_fn: Callable[[IntesisSingleUnitGateway], bool | None]
    set_fn: Callable[[IntesisSingleUnitGateway, bool], Awaitable[None]]


# How the gateway itself behaves: these stay available while it cannot reach
# the air conditioner.
GATEWAY_SWITCHES: Final[tuple[IntesisSwitchEntityDescription, ...]] = (
    IntesisSwitchEntityDescription(
        key="gateway_disabled",
        translation_key="gateway_disabled",
        report_name="control",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.gateway_disabled,
        set_fn=lambda device, on: device.async_set_gateway_disabled(on),
    ),
    IntesisSwitchEntityDescription(
        key="master",
        translation_key="master",
        report_name="diagnostics",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.is_master,
        set_fn=lambda device, on: device.async_set_master(on),
    ),
)

UNIT_SWITCHES: Final[tuple[IntesisSwitchEntityDescription, ...]] = (
    IntesisSwitchEntityDescription(
        key="remote_controller_lock",
        translation_key="remote_controller_lock",
        report_name="control",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.remote_control_disabled,
        set_fn=lambda device, on: device.async_set_remote_control_disabled(on),
    ),
)

# What the gateway is told about the room of the air conditioner. It belongs
# to that device, but the gateway holds it: it has to stay writable while the
# gateway cannot reach the air conditioner, or a window closed meanwhile would
# still count as open afterwards.
UNIT_INPUT_SWITCHES: Final[tuple[IntesisSwitchEntityDescription, ...]] = (
    IntesisSwitchEntityDescription(
        key="window_contact",
        translation_key="window_contact",
        report_name="control",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.window_contact,
        set_fn=lambda device, on: device.async_set_window_contact(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches of the gateway and its air conditioner."""
    data = entry.runtime_data
    async_add_entities(
        [
            *(
                IntesisSwitch(data.gateway, description)
                for description in GATEWAY_SWITCHES
            ),
            *(IntesisSwitch(data.unit, description) for description in UNIT_SWITCHES),
            *(
                IntesisSwitch(
                    data.gateway, description, device_info=data.unit.device_info
                )
                for description in UNIT_INPUT_SWITCHES
            ),
        ]
    )


class IntesisSwitch(IntesisEntity, SwitchEntity):
    """A setting of an Intesis gateway or of the air conditioner behind it."""

    entity_description: IntesisSwitchEntityDescription

    def __init__(
        self,
        coordinator: IntesisCoordinator | IntesisUnitCoordinator,
        description: IntesisSwitchEntityDescription,
        *,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Bind to the device the description reads, through its coordinator.

        device_info places the switch on another device than the one its
        coordinator follows.
        """
        super().__init__(coordinator, description.key, description.report_name)
        self.entity_description = description
        if device_info is not None:
            self._attr_device_info = device_info

    @property
    @override
    def is_on(self) -> bool | None:
        """The setting as the gateway reported it in the most recent poll."""
        return self.entity_description.value_fn(self.coordinator.device)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._async_write(
            lambda: self.entity_description.set_fn(self.coordinator.device, True)
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._async_write(
            lambda: self.entity_description.set_fn(self.coordinator.device, False)
        )
