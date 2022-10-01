"""Platform for Omnilogic switch integration."""
import time
from typing import Any

from omnilogic import OmniLogicException
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import OmniLogicEntity, OmniLogicUpdateCoordinator, check_guard
from .const import COORDINATOR, DOMAIN, PUMP_TYPES

SERVICE_SET_SPEED = "set_pump_speed"
OMNILOGIC_SWITCH_OFF = 7


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the light platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    entities = []

    for item_id, item in coordinator.data.items():
        id_len = len(item_id)
        item_kind = item_id[-2]
        entity_settings = SWITCH_TYPES.get((id_len, item_kind))

        if not entity_settings:
            continue

        for entity_setting in entity_settings:
            entity_classes: dict[str, type] = entity_setting["entity_classes"]
            for state_key, entity_class in entity_classes.items():
                if check_guard(state_key, item, entity_setting):
                    continue

                entity = entity_class(
                    coordinator=coordinator,
                    state_key=state_key,
                    name=entity_setting["name"],
                    kind=entity_setting["kind"],
                    item_id=item_id,
                    icon=entity_setting["icon"],
                )

                entities.append(entity)

    async_add_entities(entities)

    # register service
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_SPEED,
        {vol.Required("speed"): cv.positive_int},
        "async_set_speed",
    )


class OmniLogicSwitch(OmniLogicEntity, SwitchEntity):
    """Define an Omnilogic Base Switch entity to be extended."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        icon: str,
        item_id: tuple,
        state_key: str,
    ) -> None:
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            item_id=item_id,
            icon=icon,
        )

        self._state_key = state_key
        self._state = None
        self._last_action = 0
        self._state_delay = 30

    @property
    def is_on(self):
        """Return the on/off state of the switch."""
        state_int = 0

        # The Omnilogic API has a significant delay in state reporting after calling for a
        # change. This state delay will ensure that HA keeps an optimistic value of state
        # during this period to improve the user experience and avoid confusion.
        if self._last_action < (time.time() - self._state_delay):
            state_int = int(self.coordinator.data[self._item_id][self._state_key])

            if self._state == OMNILOGIC_SWITCH_OFF:
                state_int = 0

        self._state = state_int != 0

        return self._state


class OmniLogicRelayControl(OmniLogicSwitch):
    """Define the OmniLogic Relay entity."""

    async def async_turn_on(self, **kwargs):
        """Turn on the relay."""
        self._state = True
        self._last_action = time.time()
        self.async_write_ha_state()

        await self.coordinator.api.set_relay_valve(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            1,
        )

    async def async_turn_off(self, **kwargs):
        """Turn off the relay."""
        self._state = False
        self._last_action = time.time()
        self.async_write_ha_state()

        await self.coordinator.api.set_relay_valve(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            0,
        )


class OmniLogicPumpControl(OmniLogicSwitch):
    """Define the OmniLogic Pump Switch Entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        icon: str,
        item_id: tuple,
        state_key: str,
    ) -> None:
        """Initialize entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            icon=icon,
            item_id=item_id,
            state_key=state_key,
        )

        self._max_speed = int(coordinator.data[item_id].get("Max-Pump-Speed", 100))
        self._min_speed = int(coordinator.data[item_id].get("Min-Pump-Speed", 0))

        if "Filter-Type" in coordinator.data[item_id]:
            self._pump_type = PUMP_TYPES[coordinator.data[item_id]["Filter-Type"]]
        else:
            self._pump_type = PUMP_TYPES[coordinator.data[item_id]["Type"]]

        self._last_speed = None

    async def async_turn_on(self, **kwargs):
        """Turn on the pump."""
        self._state = True
        self._last_action = time.time()
        self.async_write_ha_state()

        on_value = 100

        if self._pump_type != "SINGLE" and self._last_speed:
            on_value = self._last_speed

        await self.coordinator.api.set_relay_valve(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            on_value,
        )

    async def async_turn_off(self, **kwargs):
        """Turn off the pump."""
        self._state = False
        self._last_action = time.time()
        self.async_write_ha_state()

        if self._pump_type != "SINGLE":
            if "filterSpeed" in self.coordinator.data[self._item_id]:
                self._last_speed = self.coordinator.data[self._item_id]["filterSpeed"]
            else:
                self._last_speed = self.coordinator.data[self._item_id]["pumpSpeed"]

        await self.coordinator.api.set_relay_valve(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            0,
        )

    async def async_set_speed(self, speed):
        """Set the switch speed."""

        if self._pump_type != "SINGLE":
            if self._min_speed <= speed <= self._max_speed:
                success = await self.coordinator.api.set_relay_valve(
                    int(self._item_id[1]),
                    int(self._item_id[3]),
                    int(self._item_id[-1]),
                    speed,
                )

                if success:
                    self.async_write_ha_state()

            else:
                raise OmniLogicException(
                    "Cannot set speed. Speed is outside pump range."
                )

        else:
            raise OmniLogicException("Cannot set speed on a non-variable speed pump.")


SWITCH_TYPES: dict[tuple[int, str], list[dict[str, Any]]] = {
    (4, "Relays"): [
        {
            "entity_classes": {"switchState": OmniLogicRelayControl},
            "name": "",
            "kind": "relay",
            "icon": None,
            "guard_condition": [],
        },
    ],
    (6, "Relays"): [
        {
            "entity_classes": {"switchState": OmniLogicRelayControl},
            "name": "",
            "kind": "relay",
            "icon": None,
            "guard_condition": [],
        }
    ],
    (6, "Pumps"): [
        {
            "entity_classes": {"pumpState": OmniLogicPumpControl},
            "name": "",
            "kind": "pump",
            "icon": None,
            "guard_condition": [],
        }
    ],
    (6, "Filter"): [
        {
            "entity_classes": {"filterState": OmniLogicPumpControl},
            "name": "",
            "kind": "pump",
            "icon": None,
            "guard_condition": [],
        }
    ],
}
