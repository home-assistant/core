"""Water heater platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature

from .const import DOMAIN, MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient
from .services import async_setup_entity_services

MODE_ENABLED = "Enabled"
MODE_DISABLED = "Disabled"
OPERATION_MODES = [MODE_ENABLED, MODE_DISABLED]


@dataclass
class LaMarzoccoWaterHeaterEntityDescriptionMixin:
    """Description of an La Marzocco Water Heater"""
    state_fn: Callable[[LaMarzoccoClient], bool]
    current_op_fn: Callable[[LaMarzoccoClient], bool]
    current_temp_fn: Callable[[LaMarzoccoClient], float | int]
    target_temp_fn: Callable[[LaMarzoccoClient], float | int]
    control_fn: Callable[[LaMarzoccoClient, bool], Coroutine[Any, Any, None]]
    set_temp_fn: Callable[[LaMarzoccoClient, float | int], Coroutine[Any, Any, None]]


@dataclass
class LaMarzoccoWaterHeaterEntityDescription(
    WaterHeaterEntityEntityDescription,
    LaMarzoccoEntityDescription,
    LaMarzoccoWaterHeaterEntityDescriptionMixin
):
    """Description of an La Marzocco Water Heater"""

    def state_fn(self, client):
        return client.current_status.get(f"{self.key}_boiler_on", False)

    def current_temp_fn(self, client):
        return client.current_status.get(f"{self.key}_temp", 0)

    def target_tmp_fn(self, client):
        return client.current_status.get(f"{self.key}_temp_set", 0)


ENTITIES: tuple[LaMarzoccoWaterHeaterEntityDescription, ...] = (
    LaMarzoccoWaterHeaterEntityDescription(
        key="coffee",
        translation_key="coffee",
        icon="mdi:water-boiler",
        min_temp=85,
        max_temp=104,
        set_temp_fn=lambda client, temp: client.set_coffee_temp(temp),
        current_op_fn=lambda client: client.current_status.get("power", False),
        control_fn=lambda client, state: client.set_coffee_boiler_on(state),
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_GS3_MP: None,
            MODEL_LM: None,
            MODEL_LMU: None
        }
    ),
    LaMarzoccoWaterHeaterEntityDescription(
        key="steam",
        translation_key="steam",
        icon="mdi:water-boiler",
        min_temp=126,
        max_temp=131,
        set_temp_fn=lambda client, temp: client.set_steam_temp(temp),
        current_op_fn=lambda client: client.current_status.get("steam_boiler_enable", False),
        control_fn=lambda client, state: client.set_steam_boiler_on(state),
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_GS3_MP: None,
            MODEL_LM: None,
            MODEL_LMU: None
        }
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up water heater type entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoWaterHeater(coordinator, hass, description)
        for description in ENTITIES
        if coordinator.lm.model_name in description.extra_attributes.keys()
    )

    await async_setup_entity_services(coordinator.lm)


class LaMarzoccoWaterHeater(LaMarzoccoEntity, WaterHeaterEntity):
    """Water heater representing espresso machine temperature data."""

    def __init__(self, coordinator, hass, entity_description):
        """Initialize water heater."""
        super().__init__(coordinator, hass, entity_description)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.ON_OFF | WaterHeaterEntityFeature.OPERATION_MODE

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def precision(self):
        """Return the precision of the platform."""
        return PRECISION_TENTHS

    @property
    def state(self):
        """State of the water heater."""
        return STATE_ELECTRIC if self.entity_description.state_fn(self._lm_client) else STATE_OFF

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.entity_description.current_temp_fn(self._lm_client)

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self.entity_description.target_temp_fn(self._lm_client)

    @property
    def operation_list(self):
        return OPERATION_MODES

    @property
    def current_operation(self):
        return MODE_ENABLED if self.entity_description.current_op_fn(self._lm_client) else MODE_DISABLED

    async def async_set_temperature(self, **kwargs):
        """Service call to set the temp of either the coffee or steam boilers."""
        temperature = kwargs.get("temperature", None)
        await self.entity_description.set_temp_fn(self._lm_client, round(temperature, 1))
        await self._update_ha_state()

    async def async_turn_on(self):
        await self.entity_description.control_fn(self._lm_client, True)

    async def async_turn_off(self):
        await self.entity_description.control_fn(self._lm_client, False)

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == MODE_ENABLED:
            await self.async_turn_on()
        else:
            await self.async_turn_off()
