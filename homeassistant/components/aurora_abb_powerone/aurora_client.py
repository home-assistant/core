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

from homeassistant.exceptions import HomeAssistantError


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
    power_in_1: float
    power_in_2: float
    temp: float
    voltage_in_1: float
    current_in_1: float
    voltage_in_2: float
    current_in_2: float
    r_iso: float
    totalenergy: float
    alarm: str


class AuroraClientError(HomeAssistantError):
    """Generic error specific to AuroraClient."""


class AuroraClientTimeoutError(AuroraClientError):
    """Timeout error specific to AuroraClient."""


class AuroraClient:
    """Abstracts aurorapy integration calls."""

    def __init__(self, client: AuroraBaseClient) -> None:
        """Initialize the AuroraClient."""
        self._client = client

    @classmethod
    def from_serial(
        cls,
        inverter_serial_address: int,
        serial_comport: str,
    ) -> AuroraClient:
        """Create an AuroraClient using serial transport."""
        client = AuroraSerialClient(
            address=inverter_serial_address,
            port=serial_comport,
            parity="N",
            timeout=1,
        )
        return cls(client)

    @classmethod
    def from_tcp(
        cls,
        inverter_serial_address: int,
        tcp_host: str,
        tcp_port: int,
    ) -> AuroraClient:
        """Create an AuroraClient using TCP transport."""
        client = AuroraTCPClient(
            ip=tcp_host,
            port=tcp_port,
            address=inverter_serial_address,
            timeout=1,
        )
        return cls(client)

    def try_connect_and_fetch_identifier(self) -> AuroraInverterIdentifier:
        """Connect to the inverter and fetch its identifier information."""
        try:
            self._client.connect()
            serial_number = self._client.serial_number()
            model = f"{self._client.version()} ({self._client.pn()})"
            firmware = self._client.firmware(1)
        except AuroraError as error:
            raise AuroraClientError(str(error)) from error
        finally:
            with contextlib.suppress(Exception):
                self._client.close()
        return AuroraInverterIdentifier(
            serial_number=serial_number,
            model=model,
            firmware=firmware,
        )

    def try_connect_and_fetch_data(self) -> AuroraInverterData:
        """Connect to the inverter and fetch current measurements."""
        try:
            self._client.connect()
            # See command 59 in the protocol manual linked in __init__.py
            grid_voltage = self._client.measure(1, True)
            grid_current = self._client.measure(2, True)
            power_watts = self._client.measure(3, True)
            frequency = self._client.measure(4)
            i_leak_dcdc = self._client.measure(6)
            i_leak_inverter = self._client.measure(7)
            power_in_1 = self._client.measure(8)
            power_in_2 = self._client.measure(9)
            temperature_c = self._client.measure(21)
            voltage_in_1 = self._client.measure(23)
            current_in_1 = self._client.measure(25)
            voltage_in_2 = self._client.measure(26)
            current_in_2 = self._client.measure(27)
            r_iso = self._client.measure(30)
            energy_wh = self._client.cumulated_energy(5)
            [alarm, *_] = self._client.alarms()
        except AuroraTimeoutError as error:
            raise AuroraClientTimeoutError(str(error)) from error
        except (SerialException, AuroraError) as error:
            raise AuroraClientError(str(error)) from error
        finally:
            with contextlib.suppress(Exception):
                self._client.close()
        return AuroraInverterData(
            grid_voltage=round(grid_voltage, 1),
            grid_current=round(grid_current, 1),
            instantaneouspower=round(power_watts, 1),
            grid_frequency=round(frequency, 1),
            i_leak_dcdc=i_leak_dcdc,
            i_leak_inverter=i_leak_inverter,
            power_in_1=round(power_in_1, 1),
            power_in_2=round(power_in_2, 1),
            temp=round(temperature_c, 1),
            voltage_in_1=round(voltage_in_1, 1),
            current_in_1=round(current_in_1, 1),
            voltage_in_2=round(voltage_in_2, 1),
            current_in_2=round(current_in_2, 1),
            r_iso=r_iso,
            totalenergy=round(energy_wh / 1000, 2),
            alarm=alarm,
        )
