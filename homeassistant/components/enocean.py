"""
EnOcean Component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/EnOcean/
"""

from abc import ABCMeta, abstractmethod
from typing import Any, Sequence, Dict

from homeassistant.core import HomeAssistant

DOMAIN = "enocean"

REQUIREMENTS = ['enocean==0.31']

CONF_DEVICE = "device"

ENOCEAN_DONGLE = None


def setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Setup the EnOcean component."""
    global ENOCEAN_DONGLE

    serial_dev = config[DOMAIN].get(CONF_DEVICE, "/dev/ttyUSB0")

    ENOCEAN_DONGLE = EnOceanDongle(hass, serial_dev)
    return True


class EnOceanDongle:
    """Representation of an EnOcean dongle."""
    from homeassistant.components.enocean import EnOceanDevice
    from enocean.protocol.packet import Packet, RadioPacket

    def __init__(self, hass: HomeAssistant, ser: str) -> None:
        """Initialize the EnOcean dongle."""
        from enocean.communicators.serialcommunicator import SerialCommunicator
        self.__communicator = SerialCommunicator(port=ser,
                                                 callback=self.callback)
        self.__communicator.start()
        self.__devices = []  # type: List[EnOceanDevice]

    def register_device(self, dev: EnOceanDevice) -> None:
        """Register another device."""
        self.__devices.append(dev)

    def send_command(self, command: Packet) -> None:
        """Send a command from the EnOcean dongle."""
        self.__communicator.send(command)

    def _combine_hex(self, data) -> int:  # pylint: disable=no-self-use
        """Combine list of integer values to one big integer."""
        output = 0x00
        for i, j in enumerate(reversed(data)):
            output |= (j << i * 8)
        return output

    # pylint: disable=too-many-branches
    def callback(self, temp: RadioPacket):
        """Callback function for EnOcean Device.

        This is the callback function called by
        python-enocan whenever there is an incoming
        packet.
        """
        from enocean.protocol.packet import RadioPacket
        # TODO: Remove test in the future in favor of gradual typing.
        if isinstance(temp, RadioPacket):
            rxtype = None
            value = None
            if temp.data[6] == 0x30:
                rxtype = "wallswitch"
                value = 1
            elif temp.data[6] == 0x20:
                rxtype = "wallswitch"
                value = 0
            elif temp.data[4] == 0x0c:
                rxtype = "power"
                value = temp.data[3] + (temp.data[2] << 8)
            elif temp.data[2] == 0x60:
                rxtype = "switch_status"
                if temp.data[3] == 0xe4:
                    value = 1
                elif temp.data[3] == 0x80:
                    value = 0
            elif temp.data[0] == 0xa5 and temp.data[1] == 0x02:
                rxtype = "dimmerstatus"
                value = temp.data[2]
            for device in self.__devices:
                if rxtype == "wallswitch" and device.stype == "listener":
                    if temp.sender == self._combine_hex(device.dev_id):
                        device.value_changed(value, temp.data[1])
                if rxtype == "power" and device.stype == "powersensor":
                    if temp.sender == self._combine_hex(device.dev_id):
                        device.value_changed(value)
                if rxtype == "power" and device.stype == "switch":
                    if temp.sender == self._combine_hex(device.dev_id):
                        if value > 10:
                            device.value_changed(1)
                if rxtype == "switch_status" and device.stype == "switch":
                    if temp.sender == self._combine_hex(device.dev_id):
                        device.value_changed(value)
                if rxtype == "dimmerstatus" and device.stype == "dimmer":
                    if temp.sender == self._combine_hex(device.dev_id):
                        device.value_changed(value)


# pylint: disable=too-few-public-methods
class EnOceanDevice(metaclass=ABCMeta):
    """Parent class for all devices associated with the EnOcean component."""

    def __init__(self) -> None:
        """Initialize the device."""
        ENOCEAN_DONGLE.register_device(self)
        self.dev_id = None
        self.stype = ""
        self.sensorid = [0x00, 0x00, 0x00, 0x00]

    # pylint: disable=no-self-use
    def send_command(self, data: Sequence[int],
                     optional: Sequence, packet_type: int):
        """Send a command via the EnOcean dongle."""
        from enocean.protocol.packet import Packet
        packet = Packet(packet_type, data=data, optional=optional)
        ENOCEAN_DONGLE.send_command(packet)

    @abstractmethod
    def value_changed(self, value: Any) -> None:
        raise NotImplementedError
