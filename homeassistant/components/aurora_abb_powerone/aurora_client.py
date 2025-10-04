"""Abstraction over aurorapy client to simplify usage in Home Assistant."""

import contextlib
from dataclasses import dataclass

from aurorapy.client import (
    AuroraBaseClient,
    AuroraError,
    AuroraSerialClient,
    AuroraTCPClient,
    AuroraTimeoutError,
)
from serial import SerialException


@dataclass
class AuroraInverterIdentifier:
    """Identifier information about the inverter."""

    serial_number: str
    model: str
    firmware: str


@dataclass
class AuroraInverterData:
    """Data (measurements) read from the inverter."""

    grid_voltage: float
    grid_current: float
    instantaneouspower: float
    grid_frequency: float
    i_leak_dcdc: float
    i_leak_inverter: float
    temp: float
    r_iso: float
    totalenergy: float
    alarm: str


class AuroraClientTimeoutError(Exception):
    """Timeout error specific to AuroraClient."""


class AuroraClientError(Exception):
    """Generic error specific to AuroraClient."""


class AuroraClient:
    """Abstracts aurorapy integration calls."""

    _client: AuroraSerialClient | AuroraTCPClient

    def __init__(self, client: AuroraBaseClient) -> None:
        """Initialize the AuroraClient with a given aurorapy client."""
        self._client = client

    @classmethod
    def from_serial(cls, inverter_serial_address: int, serial_comport: str):
        """Create an AuroraClient using a serial connection."""
        client = AuroraSerialClient(
            address=inverter_serial_address,
            port=serial_comport,
            parity="N",
            timeout=1,
        )
        return cls(client)

    @classmethod
    def from_tcp(cls, inverter_serial_address: int, tcp_host: str, tcp_port: int):
        """Create an AuroraClient using a TCP connection."""
        client = AuroraTCPClient(
            ip=tcp_host,
            port=tcp_port,
            address=inverter_serial_address,
            timeout=1,
        )
        return cls(client)

    def try_connect_and_fetch_identifier(self) -> AuroraInverterIdentifier:
        """Attempt to connect to the inverter and fetch its identifier."""
        try:
            self._client.connect()
            serial_number = self._client.serial_number()
            model = f"{self._client.version()} ({self._client.pn()})"
            firmware = self._client.firmware(1)
            return AuroraInverterIdentifier(
                serial_number=serial_number,
                model=model,
                firmware=firmware,
            )
        except AuroraError as error:
            raise AuroraClientError from error
        finally:
            # The client might be not opened properly and thus close() might raise an exception
            with contextlib.suppress(Exception):
                self._client.close()

    def try_connect_and_fetch_data(self) -> AuroraInverterData:
        """Attempt to connect to the inverter and fetch its data."""

        try:
            self._client.connect()

            # See command 59 in the protocol manual linked in __init__.py
            grid_voltage = self._client.measure(1, True)
            grid_current = self._client.measure(2, True)
            power_watts = self._client.measure(3, True)
            frequency = self._client.measure(4)
            i_leak_dcdc = self._client.measure(6)
            i_leak_inverter = self._client.measure(7)
            temperature_c = self._client.measure(21)
            r_iso = self._client.measure(30)
            energy_wh = self._client.cumulated_energy(5)
            [alarm, *_] = self._client.alarms()
        except AuroraTimeoutError as error:
            raise AuroraClientTimeoutError from error
        except (SerialException, AuroraError) as error:
            raise AuroraClientError from error
        else:
            return AuroraInverterData(
                grid_voltage=round(grid_voltage, 1),
                grid_current=round(grid_current, 1),
                instantaneouspower=round(power_watts, 1),
                grid_frequency=round(frequency, 1),
                i_leak_dcdc=i_leak_dcdc,
                i_leak_inverter=i_leak_inverter,
                temp=round(temperature_c, 1),
                r_iso=r_iso,
                totalenergy=round(energy_wh / 1000, 2),
                alarm=alarm,
            )
        finally:
            # The client might be not opened properly and thus close() might raise an exception
            with contextlib.suppress(Exception):
                self._client.close()
