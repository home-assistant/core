#!/usr/bin/env python
"""Test server for the modbus integration.

The test server allows to catch all requests and define responses.

The intention of the test server is to allow simulation of device behaivours
that often cause unexpected effects in the production code. The server makes it
easier to reproduce issues (like "modbus do not reconnect") which is inherently
difficult in the normal test suite. The test server allows the maintainer to
do a black box test between the UI and a simulated device.

The test server is living software and will be enhanced, when new issues demands
new simulations.

The test server is NOT used in the test suite, which continues to work with
pymodbus mocked.
"""
import logging
import struct

from pymodbus.compat import int2byte
from pymodbus.datastore import ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ModbusRequest, ModbusResponse
from pymodbus.server.sync import StartTcpServer

FORMAT = "%(asctime)s %(module)s:%(lineno)s %(message)s"
logging.basicConfig(format=FORMAT)
_LOGGER = logging.getLogger()


"""Configuration, adapt for simulation scenario
For most tests there are no need to change the actual code, but
simply adjust the configuration.
"""
_LOGGER.setLevel(logging.WARNING)
HOST = "localhost"
PORT = 5020


"""Custom message setup.

Define a class for each function code.
"""


class CustomBaseMessage(ModbusRequest, ModbusResponse):
    """Custom handling of modbus request.

    Request/Response are implemented as a custom class,
    allowing decode/execute/encode to be overwritten
    """

    function_code = 0x00

    def __init__(self, address=None, **kwargs):
        """Class setup."""
        super().__init__(**kwargs)
        self.address = address
        self.count = 16
        self.values = []

    def encode(self):
        """Response pdu encoding."""
        msg = f"{self.__class__.__name__} -> encoding"
        _LOGGER.warning(msg)
        result = int2byte(len(self.values) * 2)
        for register in self.values:
            result += struct.pack(">H", register)
        return result

    def decode(self, data):
        """Request pdu decoding."""
        msg = f"{self.__class__.__name__} -> decoding"
        _LOGGER.warning(msg)
        self.address, self.count = struct.unpack(">HH", data)

    def execute(self, context):
        """Request execute."""
        msg = f"{self.__class__.__name__} -> executing"
        _LOGGER.warning(msg)
        if not (1 <= self.count <= 0x7D0):
            return self.doException(ModbusException.IllegalValue)
        self.values = [20 + self.function_code]
        return self


class CM_0x01_Read_Coils(CustomBaseMessage):
    """Implement 0x01, Read Coils."""

    function_code = 0x01


class CM_0x02_Read_Discrete_Inputs(CustomBaseMessage):
    """Implement 0x02, Read Discrete Inputs."""

    function_code = 0x02


class CM_0x03_Read_Holding_Registers(CustomBaseMessage):
    """Implement 0x03, Read Holding Registers."""

    function_code = 0x03


class CM_0x04_Read_Input_Registers(CustomBaseMessage):
    """Implement 0x04, Read Input Registers."""

    function_code = 0x04


class CM_0x05_Write_Single_Coil(CustomBaseMessage):
    """Implement 0x05, Write Single Coil."""

    function_code = 0x05


class CM_0x06_Write_Single_Register(CustomBaseMessage):
    """Implement 0x06, Write Single Register."""

    function_code = 0x06


class CM_0x07_Read_Exception_Status(CustomBaseMessage):
    """Implement 0x07, Read Exception Status (Serial Line only)."""

    function_code = 0x07


class CM_0x08_Diagnostics(CustomBaseMessage):
    """Implement 0x08, Diagnostics (Serial Line only)."""

    function_code = 0x08


class CM_0x09_Reserved(CustomBaseMessage):
    """Implement 0x09, Reserved (not part of the standard)."""

    function_code = 0x09


class CM_0x0A_Reserved(CustomBaseMessage):
    """Implement 0x0A, Reserved (not part of the standard)."""

    function_code = 0x0A


class CM_0x0B_Get_Comm_Event_Counter(CustomBaseMessage):
    """Implement 0x0B, Get Comm Event Counter (Serial Line only)."""

    function_code = 0x0B


class CM_0x0C_Get_Comm_Event_Log(CustomBaseMessage):
    """Implement 0x0C, Get Comm Event Log (Serial Line only)."""

    function_code = 0x0C


class CM_0x0D_Reserved(CustomBaseMessage):
    """Implement 0x0D, Reserved (not part of the standard)."""

    function_code = 0x0D


class CM_0x0E_Reserved(CustomBaseMessage):
    """Implement 0x0E, Reserved (not part of the standard)."""

    function_code = 0x0E


class CM_0x0F_Write_Multiple_Coils(CustomBaseMessage):
    """Implement 0x0F, Write Multiple Coils."""

    function_code = 0x0F


class CM_0x10_Write_Multiple_Registers(CustomBaseMessage):
    """Implement 0x10, Write Multiple Registers."""

    function_code = 0x10


class CM_0x11_Report_Slave_ID(CustomBaseMessage):
    """Implement 0x11, Report Slave ID (Serial Line only)."""

    function_code = 0x11


class CM_0x14_Read_File_Record(CustomBaseMessage):
    """Implement 0x14, Read File Record."""

    function_code = 0x14


class CM_0x15_Write_File_Record(CustomBaseMessage):
    """Implement 0x15, Write File Record."""

    function_code = 0x15


class CM_0x16_Mask_Write_Register(CustomBaseMessage):
    """Implement 0x16, Mask Write Register."""

    function_code = 0x16


class CM_0x17_ReadWrite_Multiple_Registers(CustomBaseMessage):
    """Implement 0x17, Read/Write Multiple Registers."""

    function_code = 0x17


class CM_0x18_Read_FIFO_Queue(CustomBaseMessage):
    """Implement 0x18, Read FIFO Queue."""

    function_code = 0x18


class CM_0x29_Reserved(CustomBaseMessage):
    """Implement 0x29, # Reserved (not part of the standard)."""

    function_code = 0x29


class CM_0x2A_Reserved(CustomBaseMessage):
    """Implement 0x2A, # Reserved (not part of the standard)."""

    function_code = 0x2A


class CM_0x2B_Encapsulated_Interface_Transport(CustomBaseMessage):
    """Implement 0x2B, Encapsulated Interface Transport."""

    function_code = 0x2B


class CM_0x5A_Reserved(CustomBaseMessage):
    """Implement 0x5A, Reserved (not part of the standard)."""

    function_code = 0x5A


class CM_0x5B_Reserved(CustomBaseMessage):
    """Implement 0x5B, Reserved (not part of the standard)."""

    function_code = 0x5B


class CM_0x7D_Reserved(CustomBaseMessage):
    """Implement 0x7D, Reserved (not part of the standard)."""

    function_code = 0x7D


class CM_0x7E_Reserved(CustomBaseMessage):
    """Implement 0x7E, Reserved (not part of the standard)."""

    function_code = 0x7E


class CM_0x7F_Reserved(CustomBaseMessage):
    """Implement 0x7F, Reserved (not part of the standard)."""

    function_code = 0x7F


CUSTOMMESSAGEES = [
    CM_0x01_Read_Coils,
    CM_0x02_Read_Discrete_Inputs,
    CM_0x03_Read_Holding_Registers,
    CM_0x04_Read_Input_Registers,
    CM_0x05_Write_Single_Coil,
    CM_0x06_Write_Single_Register,
    CM_0x07_Read_Exception_Status,
    CM_0x08_Diagnostics,
    CM_0x09_Reserved,
    CM_0x0A_Reserved,
    CM_0x0B_Get_Comm_Event_Counter,
    CM_0x0C_Get_Comm_Event_Log,
    CM_0x0D_Reserved,
    CM_0x0E_Reserved,
    CM_0x0F_Write_Multiple_Coils,
    CM_0x10_Write_Multiple_Registers,
    CM_0x11_Report_Slave_ID,
    CM_0x14_Read_File_Record,
    CM_0x15_Write_File_Record,
    CM_0x16_Mask_Write_Register,
    CM_0x17_ReadWrite_Multiple_Registers,
    CM_0x18_Read_FIFO_Queue,
    CM_0x29_Reserved,
    CM_0x29_Reserved,
    CM_0x2B_Encapsulated_Interface_Transport,
    CM_0x5A_Reserved,
    CM_0x5A_Reserved,
    CM_0x7D_Reserved,
    CM_0x7E_Reserved,
    CM_0x7F_Reserved,
]


def run_server():
    """Run server."""
    context = ModbusServerContext(single=True)

    identity = ModbusDeviceIdentification()
    identity.VendorName = "home assistant modbus"
    identity.ProductCode = "HA/Modbus"
    identity.VendorUrl = "https://www.home-assistant.io"
    identity.ProductName = "Home assistant modbus Server"
    identity.ModelName = "Test Server"
    identity.MajorMinorRevision = "1.0.0"

    while True:
        StartTcpServer(
            context,
            identity=identity,
            address=(HOST, PORT),
            custom_functions=CUSTOMMESSAGEES,
        )


if __name__ == "__main__":
    run_server()
