from __future__ import annotations

from abc import ABC
import logging

from enocean.utils import combine_hex
from enocean.protocol.constants import PACKET, RORG
from enocean.protocol.packet import Packet


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


def to_degrees(temperature: int) -> float:
    """Translates temperature value from 0..255 to 0..40."""
    quotient = temperature / 255
    temperature_celsius = quotient * MAX_TARGET_TEMP
    return temperature_celsius


def translate(
    value_to_translate: str | int,
    max_value=40,
    min_value=0,
    target_max=255,
    target_min=0,
) -> int:
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
    if not isinstance(value_to_translate, int):
        value_to_translate = max_value / 2
        _LOGGER.warning(
            "Value to normalize is not a digit. Using %s instead", value_to_translate
        )
    value_to_translate = min(value_to_translate, max_value)
    value_to_translate = max(value_to_translate, min_value)

    quotient = value_to_translate / max_value

    target_value = int(target_max * quotient)
    target_value = max(target_value, target_min)
    _LOGGER.info("New target temp. value %s", str(target_value))
    return target_value


class PacketPreparator:
    def __init__(self, base_id_to_use=None):
        if base_id_to_use is None:
            base_id_to_use = [0x0, 0x0, 0x0, 0x0]
        self._next_command = None
        self._base_id_to_use = base_id_to_use
        self._optional = None
        self._command = None
        self._set_point_temp = 20
        self._run_init_sequence = False
        self._lift_set = False
        self._valve_open = False
        self._valve_closed = False
        self._summer_bit = False
        self._set_point_selection = True    # set point selection (True=1=temp (0..40), False=0= percent (0..100)
        self._set_point_inverse = True
        self._service_on = True             # True = 1 = service on, False = 0 = via RCU (room control unit)
        self._data_telegram = True          # True = 1 = data telegram, False = 0 = Teach-In-Telegram

        self.init_packet()

    @property
    def command(self):
        return self._command

    def update_target_temperature(self, new_temp):
        """Update the value of the packet which gets sent next."""
        new_temp_within_255 = translate(new_temp)

        if (translate(MIN_TARGET_TEMP) < new_temp_within_255) and (new_temp_within_255 < translate(MAX_TARGET_TEMP)):
            self._next_command[1] = hex(new_temp_within_255)
        else:
            _LOGGER.warning("Desired target temperature %s is not within the allowed range of %s..%s",
                            new_temp, MIN_TARGET_TEMP, MAX_TARGET_TEMP)

    def prepare_optional(self, optional=None) -> None:
        """Set the optional data for the packet."""
        if optional is None:
            optional = []
        self._optional = optional

    def init_packet(self) -> None:
        """Initializes the packet which will be sent."""
        packet = [0xA5, 0x00, 0x00, 0x00, 0x00]

        temp_translated = translate(
            self._set_point_temp
        )  # valve set point in celsius degrees
        packet[1] = hex(temp_translated)        # target temperature / set point temp
        packet[2] = hex(translate(20))          # current temp from RCU / thermostat

        packet[3] = hex(self.build_databyte_one())
        packet[4] = hex(self.build_databyte_two())

        self._next_command = packet

    def build_databyte_one(self):
        """Build the contents for DB1."""
        databyte = 0x00
        run_init = 1 if self._run_init_sequence else 0
        databyte |= (run_init << 7)

        lift_set = 1 if self._lift_set else 0
        databyte |= (lift_set << 6)

        valve_open = 1 if self._valve_open else 0
        databyte |= (valve_open << 5)   # works only if service is on
        if self._valve_open:
            self._valve_closed = False

        valve_closed = 1 if self._valve_closed else 0
        databyte |= (valve_closed << 4)   # works only if service is on

        summer_bit = 1 if self._summer_bit else 0
        databyte |= (summer_bit << 3)

        sp_selection = 1 if self._set_point_selection else 0
        databyte |= (sp_selection << 2)

        sp_inverse = 1 if self._set_point_inverse else 0
        databyte |= (sp_inverse << 1)

        service_on = 1 if self._service_on else 0
        databyte |= service_on

        return databyte

    def build_databyte_two(self):
        """Build the contents for DB2."""
        databyte = 0x00
        data_telegram = 1 if self._data_telegram else 0
        databyte |= (data_telegram << 3)

        return databyte


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
        self._packet_preparator = PacketPreparator()  # initializes the packet / command to send

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
                current_valve_value = packet.data[
                    1
                ]  # current value 0..100%, linear n=0..100
                _LOGGER.info("Current value: %s", str(current_valve_value))
                status = packet.data[2]
                _LOGGER.info("Status: %s", str(status))
                temperature = packet.data[3]  # Temperature 0..40°C, linear n=0..255
                self._current_temp = to_degrees(
                    temperature
                )  # update the internal state

        # send reply
        # if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
        #     self._brightness = brightness
        # response_packet: Packet = Packet.create(PACKET.RADIO_ERP1, rorg=RORG.BS4, rorg_func=0x20,
        #                              rorg_type=0x01,
        #                              sender=self._base_id_to_use,
        #                              learn=False)

        # temp_translated = translate(
        #     self._set_point_temp
        # )  # valve set point in celsius degrees

        self._packet_preparator.update_target_temperature(self._set_point_temp)

        # byte_three_temp_set_point = hex(
        #     temp_translated
        # )  # value has to be in range 0..255
        # response_packet.optional[0] = [0x3]     # send case sub-telegram number
        # response_packet.optional[1:5] = self.dev_id  # destination
        # response_packet.optional[5] = 0xFF  # dBm send case
        # response_packet.data[1] = byte_three_temp_set_point
        # response_packet.sender = self._base_id_to_use

        # rorg_func = 0x20
        # rorg_type = 0x01
        # learn = False

        command = self._packet_preparator.command
        command.extend(
            self._base_id_to_use
        )  # e.g. [0xDE, 0xAD, 0xBE, 0xEF] / sender_id
        command.extend([0x00])  # status
        self.send_command(command, [], PACKET.RADIO_ERP1)  # no optional values

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        if self.target_temperature <= self._off_value:
            return HVACMode.OFF
        if self.target_temperature > self._current_valve_value:
            return HVACMode.HEAT
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of supported modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._set_point_temp

    @property
    def target_temperature_high(self) -> float | None:
        """Return the max value of the target temperature."""
        return MAX_TARGET_TEMP

    @property
    def target_temperature_low(self) -> float | None:
        """Return the min value of the target temperature."""
        return MIN_TARGET_TEMP

    @property
    def target_temperature_step(self) -> float | None:
        """Return the step width in which the temp. can be set."""
        return TEMPERATURE_STEP

    async def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self.min_temp <= temperature <= self.max_temp:
            self._packet_preparator.update_target_temperature(temperature)
            self._set_point_temp = temperature

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
