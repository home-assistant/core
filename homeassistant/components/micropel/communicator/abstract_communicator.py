"""Abstract class of communicator."""
from .tcp_client import TcpClient


class AbstractCommunicator:
    """Abstract communicator (only interface for real implementations)."""

    def __init__(self, host, port, password):
        """Class constructor."""
        self._tcp_client = TcpClient(host, port, password)

    def close(self):
        """Disconnect client."""
        self._tcp_client.close()

    def connect(self):
        """Connect client."""
        self._tcp_client.connect()

    def read_word(self, plc, address) -> str:
        """Read word value from PLC."""
        pass

    def write_word(self, plc, address, value: int) -> str:
        """Write word value to PLC."""
        pass

    def read_bit(self, plc, address, bit_index) -> bool:
        """Read boolean value from PLC."""
        pass

    def write_bit(self, plc, address, bit_index, value: bool) -> bool:
        """Write boolean value to PLC."""
        pass
