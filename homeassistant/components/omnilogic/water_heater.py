"""Support for the Omnilogic integration pool heaters."""

from homeassistant.components.water_heater import (
    STATE_OFF,
    STATE_ON,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from .common import OmniLogicEntity, OmniLogicUpdateCoordinator
from .const import COORDINATOR, DOMAIN

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
OPERATION_LIST = [STATE_ON, STATE_OFF]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the water heater platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    entities = []

    for item_id, item in coordinator.data.items():
        id_len = len(item_id)
        item_kind = item_id[-2]
        entity_settings = WATER_HEATER_TYPES.get((id_len, item_kind))

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


class OmniLogicHeaterControl(OmniLogicEntity, WaterHeaterEntity):
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
        self._equipment_id = coordinator.data[item_id]["Operation"]["VirtualHeater"][
            "systemId"
        ]

    @property
    def temperature_unit(self):
        """Return the unit of measure for the target temp."""
        return TEMP_FAHRENHEIT

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return float(
            self.coordinator.data[self._item_id]["Operation"]["VirtualHeater"][
                "Current-Set-Point"
            ]
        )

    @property
    def max_temp(self):
        """Return the max temperature setting."""
        return float(
            self.coordinator.data[self._item_id]["Operation"]["VirtualHeater"][
                "Max-Settable-Water-Temp"
            ]
        )

    @property
    def min_temp(self):
        """Return the min temperature setting."""
        return float(
            self.coordinator.data[self._item_id]["Operation"]["VirtualHeater"][
                "Min-Settable-Water-Temp"
            ]
        )

    @property
    def supported_features(self):
        """Return the supported features of Omnilogic Heater."""
        return SUPPORT_FLAGS_HEATER

    @property
    def operation_list(self):
        """Return the operation list for the Heater."""
        return OPERATION_LIST

    @property
    def current_operation(self):
        """Return the current operation mode of the Heater."""
        current_operation = STATE_OFF

        if self.coordinator.data[self._item_id[:4]]["VirtualHeater"]["enable"] == "yes":
            current_operation = STATE_ON

        return current_operation

    @property
    def current_temperature(self):
        """Return the current water temperature."""
        backyard_id = self._item_id[:2]
        bow_id = self._item_id[:4]

        temperature = float(self.coordinator.data[bow_id]["waterTemp"])
        if self.coordinator.data[backyard_id]["Unit-of-Measurement"] == "Metric":
            hayward_temperature = round((temperature - 32) * 5 / 9, 1)
            hayward_unit_of_measure = TEMP_CELSIUS
        else:
            hayward_temperature = temperature
            hayward_unit_of_measure = TEMP_FAHRENHEIT

        self._attrs["hayward_temperature"] = hayward_temperature
        self._attrs["hayward_unit_of_measure"] = hayward_unit_of_measure

        return temperature

    @property
    def state(self):
        """Return the current state of the heater."""
        state = STATE_ON

        if self.coordinator.data[self._item_id]["heaterState"] == "0":
            state = STATE_OFF

        return state

    async def async_set_temperature(self, **kwargs):
        """Set the water heater temperature set-point."""

        success = await self.coordinator.api.set_heater_temperature(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._equipment_id),
            int(kwargs[ATTR_TEMPERATURE]),
        )

        if success:
            self.async_schedule_update_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set the water heater operating mode."""

        success = await self.coordinator.api.set_heater_onoff(
            int(self._item_id[1]),
            int(self._item_id[3]),
            int(self._equipment_id),
            operation_mode != "off",
        )

        if success:
            self.async_schedule_update_ha_state()


WATER_HEATER_TYPES = {
    (6, "Heaters"): [
        {
            "entity_classes": {"enable": OmniLogicHeaterControl},
            "name": "Heater",
            "kind": "heater",
            "icon": "mdi:water-boiler",
            "guard_condition": [],
        },
    ],
}
