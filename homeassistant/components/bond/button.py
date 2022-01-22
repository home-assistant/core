"""Support for bond buttons."""
from __future__ import annotations

import logging
from typing import Any

from bond_api import Action, BPUPSubscriptions

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BPUP_SUBS, DOMAIN, HUB
from .entity import BondEntity
from .utils import BondDevice, BondHub

_LOGGER = logging.getLogger(__name__)


BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key=Action.STOP,
        name="Stop Actions",
        icon="mdi:stop-circle-outline",
    ),
    ButtonEntityDescription(
        key=Action.TOGGLE_POWER,
        name="Toggle Power",
        icon="mdi:power-cycle",
    ),
    ButtonEntityDescription(
        key=Action.TOGGLE_LIGHT,
        name="Toggle Light",
        icon="mdi:lightbulb",
    ),
    ButtonEntityDescription(
        key=Action.INCREASE_BRIGHTNESS,
        name="Increase Brightness",
        icon="mdi:brightness-7",
    ),
    ButtonEntityDescription(
        key=Action.DECREASE_BRIGHTNESS,
        name="Decrease Brightness",
        icon="mdi:brightness-1",
    ),
    ButtonEntityDescription(
        key=Action.TOGGLE_UP_LIGHT,
        name="Toggle Up Light",
        icon="mdi:lightbulb",
    ),
    ButtonEntityDescription(
        key=Action.TOGGLE_DOWN_LIGHT,
        name="Toggle Down Light",
        icon="mdi:lightbulb",
    ),
    ButtonEntityDescription(
        key=Action.START_UP_LIGHT_DIMMER,
        name="Start Up Light Dimmer",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.START_DOWN_LIGHT_DIMMER,
        name="Start Down Light Dimmer",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.START_INCREASING_BRIGHTNESS,
        name="Start Increasing Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.START_DECREASING_BRIGHTNESS,
        name="Start Decreasing Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.INCREASE_UP_LIGHT_BRIGHTNESS,
        name="Increase Up Light Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.DECREASE_UP_LIGHT_BRIGHTNESS,
        name="Decrease Up Light Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.INCREASE_DOWN_LIGHT_BRIGHTNESS,
        name="Increase Down Light Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.DECREASE_DOWN_LIGHT_BRIGHTNESS,
        name="Decrease Down Light Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.CYCLE_DOWN_LIGHT_BRIGHTNESS,
        name="Cycle Down Light Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.CYCLE_DOWN_LIGHT_BRIGHTNESS,
        name="Cycle Down Light Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.CYCLE_BRIGHTNESS,
        name="Cycle Brightness",
        icon="mdi:brightness-percent",
    ),
    ButtonEntityDescription(
        key=Action.INCREASE_SPEED,
        name="Increase Speed",
        icon="mdi:skew-more",
    ),
    ButtonEntityDescription(
        key=Action.DECREASE_SPEED,
        name="Decrease Speed",
        icon="mdi:skew-less",
    ),
    ButtonEntityDescription(
        key=Action.TOGGLE_DIRECTION,
        name="Toggle Direction",
        icon="mdi:directions-fork",
    ),
    ButtonEntityDescription(
        key=Action.INCREASE_TEMPERATURE,
        name="Increase Temperature",
        icon="mdi:thermometer-plus",
    ),
    ButtonEntityDescription(
        key=Action.DECREASE_TEMPERATURE,
        name="Decrease Temperature",
        icon="mdi:thermometer-minus",
    ),
    ButtonEntityDescription(
        key=Action.INCREASE_FLAME,
        name="Increase Flame",
        icon="mdi:fire",
    ),
    ButtonEntityDescription(
        key=Action.DECREASE_FLAME,
        name="Decrease Flame",
        icon="mdi:fire-off",
    ),
    ButtonEntityDescription(
        key=Action.TOGGLE_OPEN,
        name="Toggle Open",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond button devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]

    async_add_entities(
        [
            BondButtonEntity(hub, device, bpup_subs, description)
            for device in hub.devices
            for description in BUTTONS
            if device.has_action(description.key)
        ],
        True,
    )


class BondButtonEntity(BondEntity, ButtonEntity):
    """Bond Button Device."""

    def __init__(
        self,
        hub: BondHub,
        device: BondDevice,
        bpup_subs: BPUPSubscriptions,
        description: ButtonEntityDescription,
    ) -> None:
        """Init Bond button."""
        super().__init__(hub, device, bpup_subs, description.name)
        self.entity_description = description

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        await self._hub.bond.action(
            self._device.device_id, Action(self.entity_description.key)
        )

    def _apply_state(self, state: dict) -> None:
        """Apply the state."""
