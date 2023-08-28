"""Support for bond buttons."""
from __future__ import annotations

from dataclasses import dataclass

from bond_async import Action, BPUPSubscriptions

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice, BondHub

# The api requires a step size even though it does not
# seem to matter what is is as the underlying device is likely
# getting an increase/decrease signal only
STEP_SIZE = 10


@dataclass
class BondButtonEntityDescriptionMixin:
    """Mixin to describe a Bond Button entity."""

    mutually_exclusive: Action | None
    argument: int | None


@dataclass
class BondButtonEntityDescription(
    ButtonEntityDescription, BondButtonEntityDescriptionMixin
):
    """Class to describe a Bond Button entity."""

    # BondEntity does not support UNDEFINED,
    # restrict the type to str | None
    name: str | None = None


STOP_BUTTON = BondButtonEntityDescription(
    key=Action.STOP,
    name="Stop Actions",
    icon="mdi:stop-circle-outline",
    mutually_exclusive=None,
    argument=None,
)


BUTTONS: tuple[BondButtonEntityDescription, ...] = (
    BondButtonEntityDescription(
        key=Action.TOGGLE_POWER,
        name="Toggle Power",
        icon="mdi:power-cycle",
        mutually_exclusive=Action.TURN_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_LIGHT,
        name="Toggle Light",
        icon="mdi:lightbulb",
        mutually_exclusive=Action.TURN_LIGHT_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_BRIGHTNESS,
        name="Increase Brightness",
        icon="mdi:brightness-7",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_BRIGHTNESS,
        name="Decrease Brightness",
        icon="mdi:brightness-1",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_UP_LIGHT,
        name="Toggle Up Light",
        icon="mdi:lightbulb",
        mutually_exclusive=Action.TURN_UP_LIGHT_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_DOWN_LIGHT,
        name="Toggle Down Light",
        icon="mdi:lightbulb",
        mutually_exclusive=Action.TURN_DOWN_LIGHT_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_DIMMER,
        name="Start Dimmer",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_UP_LIGHT_DIMMER,
        name="Start Up Light Dimmer",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_DOWN_LIGHT_DIMMER,
        name="Start Down Light Dimmer",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_INCREASING_BRIGHTNESS,
        name="Start Increasing Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_DECREASING_BRIGHTNESS,
        name="Start Decreasing Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_UP_LIGHT_BRIGHTNESS,
        name="Increase Up Light Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_UP_LIGHT_BRIGHTNESS,
        name="Decrease Up Light Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_DOWN_LIGHT_BRIGHTNESS,
        name="Increase Down Light Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_DOWN_LIGHT_BRIGHTNESS,
        name="Decrease Down Light Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.CYCLE_UP_LIGHT_BRIGHTNESS,
        name="Cycle Up Light Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.CYCLE_DOWN_LIGHT_BRIGHTNESS,
        name="Cycle Down Light Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.CYCLE_BRIGHTNESS,
        name="Cycle Brightness",
        icon="mdi:brightness-percent",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_SPEED,
        name="Increase Speed",
        icon="mdi:skew-more",
        mutually_exclusive=Action.SET_SPEED,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_SPEED,
        name="Decrease Speed",
        icon="mdi:skew-less",
        mutually_exclusive=Action.SET_SPEED,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_DIRECTION,
        name="Toggle Direction",
        icon="mdi:directions-fork",
        mutually_exclusive=Action.SET_DIRECTION,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_TEMPERATURE,
        name="Increase Temperature",
        icon="mdi:thermometer-plus",
        mutually_exclusive=None,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_TEMPERATURE,
        name="Decrease Temperature",
        icon="mdi:thermometer-minus",
        mutually_exclusive=None,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_FLAME,
        name="Increase Flame",
        icon="mdi:fire",
        mutually_exclusive=None,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_FLAME,
        name="Decrease Flame",
        icon="mdi:fire-off",
        mutually_exclusive=None,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_OPEN,
        name="Toggle Open",
        mutually_exclusive=Action.OPEN,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_POSITION,
        name="Increase Position",
        icon="mdi:plus-box",
        mutually_exclusive=Action.SET_POSITION,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_POSITION,
        name="Decrease Position",
        icon="mdi:minus-box",
        mutually_exclusive=Action.SET_POSITION,
        argument=STEP_SIZE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond button devices."""
    data: BondData = hass.data[DOMAIN][entry.entry_id]
    hub = data.hub
    bpup_subs = data.bpup_subs
    entities: list[BondButtonEntity] = []

    for device in hub.devices:
        device_entities = [
            BondButtonEntity(hub, device, bpup_subs, description)
            for description in BUTTONS
            if device.has_action(description.key)
            and (
                description.mutually_exclusive is None
                or not device.has_action(description.mutually_exclusive)
            )
        ]
        if device_entities and device.has_action(STOP_BUTTON.key):
            # Most devices have the stop action available, but
            # we only add the stop action button if we add actions
            # since its not so useful if there are no actions to stop
            device_entities.append(
                BondButtonEntity(hub, device, bpup_subs, STOP_BUTTON)
            )
        entities.extend(device_entities)

    async_add_entities(entities)


class BondButtonEntity(BondEntity, ButtonEntity):
    """Bond Button Device."""

    entity_description: BondButtonEntityDescription

    def __init__(
        self,
        hub: BondHub,
        device: BondDevice,
        bpup_subs: BPUPSubscriptions,
        description: BondButtonEntityDescription,
    ) -> None:
        """Init Bond button."""
        self.entity_description = description
        super().__init__(
            hub, device, bpup_subs, description.name, description.key.lower()
        )

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.argument:
            action = Action(
                self.entity_description.key, self.entity_description.argument
            )
        else:
            action = Action(self.entity_description.key)
        await self._hub.bond.action(self._device.device_id, action)

    def _apply_state(self) -> None:
        """Apply the state."""
