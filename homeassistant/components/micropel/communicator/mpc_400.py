"""MPC400 PLC and communicator."""
from ..helper import convert
from ..helper.message import Message
from .abstract_communicator import AbstractCommunicator


class Mpc400(AbstractCommunicator):
    """MPC400 implementation."""

    def read_word(self, plc, address) -> str:
        """Read word value from PLC."""
        message = Message.build_message(
            plc, "*", 0x2E, convert.int_to_hex(address, 8) + convert.int_to_hex(0x81, 2)
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 4 : len(data)]
        return "0x" + value

    def write_word(self, plc, address, value: int) -> str:
        """Write word value to PLC."""
        message = Message.build_message(
            plc,
            "*",
            0x2F,
            convert.int_to_hex(address, 8)
            + convert.int_to_hex(0x81, 2)
            + convert.int_to_hex(value, 4),
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 4 : len(data)]
        return "0x" + str(value)

    def read_bit(self, plc, address, bit_index) -> bool:
        """Read boolean value from PLC."""
        message = Message.build_message(
            plc,
            "*",
            0x2E,
            convert.int_to_hex(address, 8) + convert.int_to_hex(bit_index, 2),
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 2 : len(data)]
        return int(value) == 1

    def write_bit(self, plc, address, bit_index, value: bool) -> bool:
        """Write boolean value to PLC."""
        value_int = 0  # 0000
        if value:
            value_int = 8  # 1000
        ctrl = bit_index + value_int
        message = Message.build_message(
            plc, "*", 0x2F, convert.int_to_hex(address, 8) + convert.int_to_hex(ctrl, 2)
        )
        data = self._tcp_client.send_and_receive(message)
        value = data[len(data) - 2 : len(data)]
        return int(value) == 1
