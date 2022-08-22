"""A representation of a Kieback & Peter MD15-FTL or a compatible device speaking EEP A5-20-01."""
from __future__ import annotations

from abc import ABC
import logging

from components.climate import HVACAction
from components.enocean.device import EnOceanEntity
from enocean import utils
from enocean.protocol.constants import PACKET, RORG
from enocean.protocol.packet import Packet
from enocean.utils import combine_hex

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_ID, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

MAX_TARGET_TEMP = 40.0
MIN_TARGET_TEMP = 0.0
TEMPERATURE_STEP = 1

DEFAULT_SET_POINT = 20.0

CONF_SET_POINT_INVERSE = "inverse"
CONF_SENDER_ID = "sender_id"

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
    set_point_inverse = config.get(CONF_SET_POINT_INVERSE, False)

    add_entities(
        [EnOceanThermostat(base_id_to_use, dev_id, dev_name, set_point_inverse)]
    )


def to_degrees(temperature: int) -> float:
    """Translate temperature value from 0..255 to 0..40."""
    quotient = temperature / 255
    temperature_celsius = quotient * MAX_TARGET_TEMP
    return temperature_celsius


def translate(
    value_to_translate: str | float | int,
    max_value=40.0,
    min_value=0.0,
    target_max=255,
    target_min=0,
) -> int:
    """Translate value in celsius degrees to a value in the target range.

    If the value exceeds the lower or upper bound, it gets adjusted. If it's not a digit,
    a default value will be set.
    :param target_min: The minimal value which can be returned
    :param target_max: The maximal value which can be returned
    :param min_value: The minimal value which will be translated
    :param max_value: The maximal value which will be translated
    :param value_to_translate
    :rtype int
    """
    if not isinstance(value_to_translate, float):
        value_to_translate = max_value / 2
        _LOGGER.warning(
            "Value to normalize is not a digit. Using %s instead", value_to_translate
        )
    value_to_translate = min(value_to_translate, max_value)
    value_to_translate = max(value_to_translate, min_value)

    quotient = value_to_translate / max_value

    translated_value = int(target_max * quotient)
    translated_value = max(translated_value, target_min)
    return translated_value


class PacketPreparator:
    """Prepares radio packets which will be sent."""

    def __init__(self, base_id_to_use=None):
        """Additionally to basic init, the initialization of the packet to sent, will be done."""
        if base_id_to_use is None:
            base_id_to_use = [0x0, 0x0, 0x0, 0x0]
        self._next_command = None
        self._base_id_to_use = base_id_to_use
        self._optional = None
        self._command = None
        self._set_point_temp = DEFAULT_SET_POINT
        self._run_init_sequence = False
        self._lift_set = False
        self._valve_open = False
        self._valve_closed = False
        self._summer_bit = False
        self._set_point_selection = (
            True  # set point selection (True=1=temp (0..40), False=0= percent (0..100)
        )
        self._set_point_inverse = True
        self._service_on = (
            True  # True = 1 = service on, False = 0 = via RCU (room control unit)
        )
        self._data_telegram = (
            True  # True = 1 = data telegram, False = 0 = Teach-In-Telegram
        )
        self._is_heating = False

        self.init_packet()

    @property
    def command(self):
        """Return the next command that shall be sent.

        It gets sent via the communicator right after receiving
        a packet from the thermostat.
        """
        return self._next_command

    def update_target_temperature(self, new_temp):
        """Update the value of the packet which gets sent next."""
        new_temp_within_255 = translate(new_temp)

        if translate(
            MIN_TARGET_TEMP
        ) > new_temp_within_255 or new_temp_within_255 > translate(MAX_TARGET_TEMP):
            _LOGGER.warning(
                "Desired target temperature %s is not within the allowed range of %s..%s",
                new_temp,
                MIN_TARGET_TEMP,
                MAX_TARGET_TEMP,  # self._current_valve_value = 0
            )
        else:
            self._next_command[1] = new_temp_within_255

    def init_packet(self) -> None:
        """Initialize the packet which will be sent."""
        packet = [0xA5, 0x00, 0x00, 0x00, 0x00]

        temp_translated = translate(
            self._set_point_temp
        )  # valve set point in celsius degrees
        packet[1] = temp_translated  # target temperature / set point temp
        packet[2] = translate(DEFAULT_SET_POINT)  # current temp from RCU / thermostat

        packet[3] = self.build_databyte_one()
        packet[4] = self.build_databyte_two()

        self._next_command = packet

    def build_databyte_one(self):
        """Build the contents for DB1."""
        databyte = 0x00
        run_init = 1 if self._run_init_sequence else 0
        databyte |= run_init << 7

        lift_set = 1 if self._lift_set else 0
        databyte |= lift_set << 6

        valve_open = 1 if self._valve_open else 0
        databyte |= valve_open << 5  # works only if service is on
        if self._valve_open:
            self._valve_closed = False

        valve_closed = 1 if self._valve_closed else 0
        databyte |= valve_closed << 4  # works only if service is on

        summer_bit = 1 if self._summer_bit else 0
        databyte |= summer_bit << 3

        sp_selection = 1 if self._set_point_selection else 0
        databyte |= sp_selection << 2

        sp_inverse = 1 if self._set_point_inverse else 0
        databyte |= sp_inverse << 1

        service_on = 1 if self._service_on else 0
        databyte |= service_on

        return databyte

    def build_databyte_two(self):
        """Build the contents for DB2."""
        databyte = 0x00
        data_telegram = 1 if self._data_telegram else 0
        databyte |= data_telegram << 3

        return databyte

    def update_set_point_inverse(self, set_point_inverse):
        """Update the value if the set point shall be interpreted inverse."""
        self._set_point_inverse = set_point_inverse
        self._next_command[3] = self.build_databyte_one()


class EnOceanThermostat(EnOceanEntity, ClimateEntity, ABC):
    """Representation of an EnOcean Thermostat."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, base_id_to_use, dev_id, dev_name, set_point_inverse=False):
        """Initialize the EnOcean Thermostat source."""
        super().__init__(dev_id, dev_name)
        self._base_id_to_use = base_id_to_use
        self._set_point_temp = DEFAULT_SET_POINT
        self._current_temp: float = DEFAULT_SET_POINT
        self._off_value = 0
        self._attr_unique_id = f"{combine_hex(dev_id)}"
        self.entity_description = ClimateEntityDescription(
            key="thermostat",
            name=dev_name,
        )
        self._packet_preparator = (
            PacketPreparator()
        )  # initializes the packet / command to send
        self._packet_preparator.update_set_point_inverse(set_point_inverse)

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
                _LOGGER.debug(
                    "Data from thermo arrived: %s", utils.to_hex_string(packet.data)
                )
                current_vale_value = packet.data[
                    1
                ]  # current value 0..100%, linear n=0..100
                _LOGGER.debug(
                    "Current valve value in percent (0=closed): %s",
                    str(current_vale_value),
                )
                status = packet.data[2]
                _LOGGER.debug("Status as int: %s", str(status))
                temperature = packet.data[3]  # Temperature 0..40°C, linear n=0..255
                self._current_temp = to_degrees(
                    temperature
                )  # update the internal state

        self._packet_preparator.update_target_temperature(self._set_point_temp)

        command = self._packet_preparator.command
        command.extend(
            self._base_id_to_use
        )  # e.g. [0xDE, 0xAD, 0xBE, 0xEF] / sender_id
        command.extend([0x00])  # status
        _LOGGER.debug("Packet sent: %s", str(command))
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
        if self.target_temperature > self._set_point_temp:
            return HVACMode.HEAT
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of supported modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def supported_features(self) -> int:
        """Return the feature set."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def hvac_action(self) -> HVACAction | str | None:
        """Return the current HVAC Action."""
        if self._current_temp > self._set_point_temp:
            return HVACAction.OFF
        if self._current_temp <= self._set_point_temp:
            return HVACAction.HEATING
        return None

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

    def set_temperature(self, **kwargs) -> None:
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
            self._set_point_temp = MAX_TARGET_TEMP
        if hvac_mode == HVACMode.OFF:
            self._set_point_temp = MIN_TARGET_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum value to set."""
        return MAX_TARGET_TEMP

    @property
    def min_temp(self) -> float:
        """Return the minimum value to set."""
        return MIN_TARGET_TEMP
