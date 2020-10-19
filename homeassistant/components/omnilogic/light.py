"""Platform for light integration."""
import logging
import time

from omnilogic import LightEffect, OmniLogicException
import voluptuous as vol

from homeassistant.components.light import ATTR_EFFECT, SUPPORT_EFFECT, LightEntity
from homeassistant.helpers import entity_platform

from .common import OmniLogicEntity, OmniLogicUpdateCoordinator
from .const import COORDINATOR, DOMAIN

SERVICE_SET_V2EFFECT = "set_v2_lights"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the light platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    entities = []

    for item_id, item in coordinator.data.items():
        id_len = len(item_id)
        item_kind = item_id[-2]
        entity_settings = LIGHT_TYPES.get((id_len, item_kind))

        if not entity_settings:
            continue

        for entity_setting in entity_settings:
            for state_key, entity_class in entity_setting["entity_classes"].items():
                if state_key not in item:
                    continue

                guard = False
                for guard_condition in entity_setting["guard_condition"]:
                    if guard_condition and all(
                        item.get(guard_key) == guard_value
                        for guard_key, guard_value in guard_condition.items()
                    ):
                        guard = True

                if guard:
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
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_V2EFFECT,
        {
            vol.Optional("brightness"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=4)
            ),
            vol.Optional("speed"): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
        },
        "async_set_v2effect",
    )


class OmniLogicLightControl(OmniLogicEntity, LightEntity):
    """Define an Omnilogic Water Heater entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        icon: str,
        item_id: tuple,
        state_key: str,
    ):
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            item_id=item_id,
            icon=icon,
        )

        self._state_key = state_key
        self._wait_for_state_change = False
        if coordinator.data[item_id]["V2"] == "yes":
            self._version = 2
            self._brightness = 4
            self._speed = 4
        else:
            self._version = 1

    @property
    def is_on(self):
        """Return if the light is on."""

        if self._version == 2:
            self._attrs["brightness"] = self.coordinator.data[self._item_id][
                "brightness"
            ]
            self._attrs["speed"] = self.coordinator.data[self._item_id]["speed"]

        return int(self.coordinator.data[self._item_id][self._state_key])

    @property
    def effect(self):
        """Return the current light effect."""
        effect = LightEffect(self.coordinator.data[self._item_id]["currentShow"])
        return effect.name

    @property
    def effect_list(self):
        """Return the supported light effects."""
        if self._version == 2:
            return list(LightEffect.__members__)
        else:
            return list(LightEffect.__members__)[:17]

    @property
    def supported_features(self):
        """Return the list of supported features of the light."""
        return SUPPORT_EFFECT

    async def async_set_effect(self, effect):
        """Set the light show effect."""
        success = await self.coordinator.api.set_lightshow(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            int(LightEffect[effect].value),
        )

        if success:
            self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        if kwargs.get(ATTR_EFFECT):
            await self.async_set_effect(kwargs[ATTR_EFFECT])

        success = await self.coordinator.api.set_relay_valve(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            1,
        )

        if success:
            time.sleep(30)
            self.async_schedule_update_ha_state(True)

    async def async_turn_off(self):
        """Turn off the light."""
        success = await self.coordinator.api.set_relay_valve(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._item_id[-1]),
            0,
        )

        if success:
            time.sleep(60)
            self.async_schedule_update_ha_state(True)

    async def async_set_v2effect(self, **kwargs):
        """Set the light effect speed or brightness for V2 lights."""

        if self._version == 2:
            speed = kwargs.get("speed", self._speed)
            brightness = kwargs.get("brightness", self._brightness)
            if 0 <= speed <= 8 and 0 <= brightness <= 4:
                success = await self.coordinator.api.set_lightshowv2(
                    int(self._item_id[1]),
                    int(self._item_it[3]),
                    int(self._item_id[-1]),
                    int(self.coordinator.data[self._item_id]["currentShow"]),
                    speed,
                    brightness,
                )

                if success:
                    time.sleep(30)
                    self.async_schedule_update_ha_state(True)
            else:
                raise OmniLogicException("Speed must be 0-8 and brightness 0-4.")
        else:
            raise OmniLogicException(
                "Cannot set effect speed or brightness on version 1 lights."
            )


LIGHT_TYPES = {
    (6, "Lights"): [
        {
            "entity_classes": {"lightState": OmniLogicLightControl},
            "name": "",
            "kind": "lights",
            "icon": None,
            "guard_condition": [],
        },
    ],
}
