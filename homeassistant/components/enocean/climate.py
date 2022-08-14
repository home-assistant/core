from __future__ import annotations

from abc import ABC
import logging

from enocean.protocol.constants import PACKET, RORG
from enocean.protocol.packet import Packet, RadioPacket
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

_LOGGER = logging.getLogger(__name__)


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

    def __init__(self, base_id_to_use=[0x0, 0x0, 0x0, 0x0]):
        self._base_id_to_use = base_id_to_use
        self._optional = None
        self._command = None
        self._set_point_temp = 20

        # TODO: built optional
        self.prepare_optional()

    @property
    def optional(self):
        return self._optional

    @property
    def command(self):
        return self._command

    def prepare_next_packet(self):
        temp_translated = translate(self._set_point_temp)  # valve set point in celsius degrees
        byte_three = hex(temp_translated)  # value has to be in range 0..255
        byte_two = 0x00  # temperature actual from RCU = 0b0
        byte_one_bit_seven = 0  # run init sequence
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
        # self._data = data_to_set

    def update_optional(self):
        pass

    def update_target_temperature(self):
        pass

    def prepare_optional(self, optional=None) -> None:
        """Set the optional data for the packet."""
        if optional is None:
            optional = []
        self._optional = optional


def translate(value_to_translate: str | int, max_value=40, min_value=0, target_max=255, target_min=0) -> int:
    """Translates value in celsius degrees to a value in the target range.

    If the value exceeds the lower or upper bound, it get's adjusted. If it's not a digit,
    a default value will be set.
    :param target_min: The minimal value which can be returned
    :param target_max: The maximal value which can be returned
    :param min_value: The minimal value which will be translated
    :param max_value: The maximal value which will be translated
    :param value_to_translate
    :rtype int
    """
    if not value_to_translate.isdigit():
        value_to_translate = max_value / 2
        _LOGGER.warning("Value to normalize is not a digit. Using %s instead", value_to_translate)
    value_to_translate = min(value_to_translate, max_value)
    value_to_translate = max(value_to_translate, min_value)

    quotient = value_to_translate / max_value

    target_value = int(target_max * quotient)
    target_value = max(target_value, target_min)
    _LOGGER.info("New target temp. value %s", str(target_value))
    return target_value


def to_degrees(temperature: int) -> float:
    """Translates temperature value from 0..255 to 0..40."""
    quotient = temperature / 255
    temperature_celsius = quotient * MAX_TARGET_TEMP
    return temperature_celsius


class EnOceanThermostat(EnOceanEntity, ClimateEntity, ABC):
    """Representation of an EnOcean Thermostat."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, base_id_to_use, dev_id, dev_name):
        """Initialize the EnOcean Thermostat source."""
        super().__init__(dev_id, dev_name)
        self._base_id_to_use = base_id_to_use
        self._set_point_temp = DEFAULT_SET_POINT
        self._current_temp: float = 0
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
            # if packet.data[-5:-1] == [1, 1, 222, 176]:
            if packet.data[-5:-1] == self.dev_id:
                # this packet is for the current device

                # data could be sth. like: A5:00:90:95:08:01:01:DE:B0:00
                current_valve_value = packet.data[1]  # current value 0..100%, linear n=0..100
                _LOGGER.info("Current value: %s", str(current_valve_value))
                status = packet.data[2]
                _LOGGER.info("Status: %s", str(status))
                temperature = packet.data[3]  # Temperature 0..40°C, linear n=0..255
                self._current_temp = to_degrees(temperature)  # update the internal state

        # send reply
        # if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
        #     self._brightness = brightness
        # response_packet: Packet = Packet.create(PACKET.RADIO_ERP1, rorg=RORG.BS4, rorg_func=0x20,
        #                              rorg_type=0x01,
        #                              sender=self._base_id_to_use,
        #                              learn=False)

        temp_translated = translate(self._set_point_temp)   # valve set point in celsius degrees
        byte_three_temp_set_point = hex(temp_translated)    # value has to be in range 0..255
        # response_packet.optional[0] = [0x3]     # send case sub-telegram number
        # response_packet.optional[1:5] = self.dev_id  # destination
        # response_packet.optional[5] = 0xFF  # dBm send case
        # response_packet.data[1] = byte_three_temp_set_point
        # response_packet.sender = self._base_id_to_use

        byte_two_temp_from_rcu = temperature  # use the internal value for now
        byte_one_settings = 0x07
        byte_zero_not_used_data_telegram = 0x08

        # rorg_func = 0x20
        # rorg_type = 0x01
        # learn = False

        command = [0xA5,                                # packet type 4BS
                   byte_three_temp_set_point,           # target_temperature
                   byte_two_temp_from_rcu,              # settings
                   byte_one_settings,                   # settings
                   byte_zero_not_used_data_telegram]
        command.extend(self._base_id_to_use)  # e.g. [0xDE, 0xAD, 0xBE, 0xEF] / sender_id
        command.extend([0x00])  # status
        # self.send_command(command, [], 0x01)
        self.send_command(command, [], PACKET.RADIO_ERP1)


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
        return self._set_point_temp

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
            self._set_point_temp = temperature
            # TODO: set it in the next packet to send
            # await self._packet_preparator.update_target_temperature(temperature)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode.
        :type hvac_mode: HVACMode
        """
        if hvac_mode == HVACMode.HEAT:
            self.turn_on()
        if hvac_mode == HVACMode.OFF:
            self.turn_off()

    def turn_off(self):
        # TODO: do sth.
        pass

    def turn_on(self):
        # TODO: do sth.
        pass
