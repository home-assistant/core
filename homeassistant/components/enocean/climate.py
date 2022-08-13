from __future__ import annotations

from abc import ABC

from enocean.protocol.constants import PACKET, RORG
from enocean.protocol.packet import Packet
from enocean.utils import combine_hex

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    ClimateEntityDescription,
)
from homeassistant.components.enocean.device import EnOceanEntity
from homeassistant.components.enocean.light import CONF_SENDER_ID
from homeassistant.const import CONF_ID, CONF_NAME, TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.core import HomeAssistant

MAX_TARGET_TEMP = 40
MIN_TARGET_TEMP = 0
TEMPERATURE_STEP = 1

BASE_ID_TO_USE = "sender_base_id"
DEFAULT_SET_POINT = 20


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean thermostat platform."""
    sender_id = config.get(CONF_SENDER_ID, [0x0, 0x0, 0x0, 0x0])
    dev_name = config.get(CONF_NAME, "EnOcean Thermostat A5-20-01")
    dev_id = config.get(CONF_ID, [0x0, 0x0, 0x0, 0x0])
    base_id_to_use = sender_id

    add_entities([EnOceanThermostat(base_id_to_use, dev_id, dev_name)])


class PacketPreparator:

    def __init__(self):
        self._optional = None
        self._data = None

    @property
    def optional(self):
        return self._optional

    @property
    def data(self):
        return self._data

    def prepare_next_packet(self):
        byte_three = 0x80  # 128 -> 20°  valve set point in celsius degrees
        byte_two = 0x00   # temperature actual from RCU = 0b0
        byte_one_bit_seven = 0 # run init sequence
        byte_one_bit_six = 0  # lift set
        byte_one_bit_five = 0  # valve open
        byte_one_bit_four = 0  # valve closed
        byte_one_bit_three = 0  # summer bit
        byte_one_bit_two = 1  # set point selection (1 = temp (0-40), 0 = percent (0-100)
        byte_one_bit_one = 0  # set point inverse
        byte_one_bit_zero = 0  # 0 = RCU, 1 = service on
        data_to_set = []
        data_to_set[0] = byte_three
        data_to_set[1] = byte_two
        # TODO: set data_to_set[0] via bit shifting
        data_to_set[2] = 0x0 | (byte_one_bit_seven << 7)
        data_to_set[2] = 0x0 | (byte_one_bit_six << 6)
        data_to_set[2] = 0x0 | (byte_one_bit_five << 5)
        data_to_set[2] = 0x0 | (byte_one_bit_four << 4)
        data_to_set[2] = 0x0 | (byte_one_bit_three << 3)
        data_to_set[2] = 0x0 | (byte_one_bit_two << 2)
        data_to_set[2] = 0x0 | (byte_one_bit_one << 1)
        data_to_set[2] = 0x0 | byte_one_bit_zero
        self._data = data_to_set


    def update_optional(self):
        pass

    def update_target_temperature(self):
        pass


class EnOceanThermostat(EnOceanEntity, ClimateEntity, ABC):
    """Representation of an EnOcean Thermostat"""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, base_id_to_use, dev_id, dev_name):
        """Initialize the EnOcean Thermostat source."""
        super().__init__(dev_id, dev_name)
        self._base_id_to_use = base_id_to_use
        self._set_point = DEFAULT_SET_POINT
        self._current_temp = 0
        self._off_value = 0
        self._current_valve_value = 0
        self._attr_unique_id = f"{combine_hex(dev_id)}"
        self.entity_description = ClimateEntityDescription(
            key="thermostat",
            name=dev_name,
        )
        self._packet_preparator = PacketPreparator()
        self._packet_preparator.prepare_next_packet()

    def value_changed(self, packet: Packet):
        """Update the internal state of the device.

         When a packet arrives, update the state and immediately send the response.
         """
        # extract data and update values
        if packet.rorg == RORG.BS4:
            pass



        # send reply
        self.send_command(self._packet_preparator.data, self._packet_preparator.optional, PACKET.RADIO_ERP1)

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        if self.target_temperature <= self._off_value:
            return HVACMode.OFF
        if self.target_temperature > self._current_valve_value:
            return HVACMode.HEAT
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def current_temperature(self) -> float | None:
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        return self._set_point

    @property
    def target_temperature_high(self) -> float | None:
        return MAX_TARGET_TEMP

    @property
    def target_temperature_low(self) -> float | None:
        return MIN_TARGET_TEMP

    @property
    def target_temperature_step(self) -> float | None:
        return TEMPERATURE_STEP

    async def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self.min_temp <= temperature <= self.max_temp:
            await self._packet_preparator.update_target_temperature(temperature)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode.
        :type hvac_mode: HVACMode
        """
        if hvac_mode == HVACMode.HEAT:
            self.turn_on()
        if hvac_mode == HVACMode.OFF:
            self.turn_off()

    def turn_off(self):
        pass

    def turn_on(self):
        pass
