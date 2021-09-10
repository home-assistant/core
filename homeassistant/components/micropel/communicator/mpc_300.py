"""MPC300 PLC and communicator."""
from ..helper import convert
from ..helper.message import Message
from .abstract_communicator import AbstractCommunicator


class Mpc300(AbstractCommunicator):
    """MPC300 implementation."""

    def read_word(self, plc, address) -> str:
        """Read word value from PLC."""
        message = Message.build_message(plc, "*", 0x44, convert.int_to_hex(address, 4))
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 4 : len(data)]
        return "0x" + value

    def write_word(self, plc, address, value: int) -> str:
        """Write word value to PLC."""
        message = Message.build_message(
            plc,
            "*",
            0x45,
            convert.int_to_hex(address, 4) + convert.int_to_hex(value, 4),
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 4 : len(data)]
        return "0x" + str(value)

    def read_bit(self, plc, address, bit_index) -> bool:
        """Read boolean value from PLC."""
        mask = 2 ** bit_index
        message = Message.build_message(
            plc, "*", 0x2A, convert.int_to_hex(address, 4) + convert.int_to_hex(mask, 2)
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 2 : len(data)]
        return int(value) == 1

    def write_bit(self, plc, address, bit_index, value: bool) -> bool:
        """Write boolean value to PLC."""
        mask = 2 ** bit_index
        value_int = 0
        if value:
            value_int = 1
        message = Message.build_message(
            plc,
            "*",
            0x2B,
            convert.int_to_hex(address, 4)
            + convert.int_to_hex(mask, 2)
            + convert.int_to_hex(value_int, 2),
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 2 : len(data)]
        return int(value) == 1
