"""Tests for the Oncue integration."""
from contextlib import contextmanager
from unittest.mock import patch

from aiooncue import OncueDevice, OncueSensor

MOCK_ASYNC_FETCH_ALL = {
    "123456": OncueDevice(
        name="My Generator",
        state="Off",
        product_name="RDC 2.4",
        hardware_version="319",
        serial_number="SERIAL",
        sensors={
            "Product": OncueSensor(
                name="Product",
                display_name="Controller Type",
                value="RDC 2.4",
                display_value="RDC 2.4",
                unit=None,
            ),
            "FirmwareVersion": OncueSensor(
                name="FirmwareVersion",
                display_name="Current Firmware",
                value="2.0.6",
                display_value="2.0.6",
                unit=None,
            ),
            "LatestFirmware": OncueSensor(
                name="LatestFirmware",
                display_name="Latest Firmware",
                value="2.0.6",
                display_value="2.0.6",
                unit=None,
            ),
            "EngineSpeed": OncueSensor(
                name="EngineSpeed",
                display_name="Engine Speed",
                value="0",
                display_value="0 R/min",
                unit="R/min",
            ),
            "EngineOilPressure": OncueSensor(
                name="EngineOilPressure",
                display_name="Engine Oil Pressure",
                value=0,
                display_value="0 Psi",
                unit="Psi",
            ),
            "EngineCoolantTemperature": OncueSensor(
                name="EngineCoolantTemperature",
                display_name="Engine Coolant Temperature",
                value=32,
                display_value="32 F",
                unit="F",
            ),
            "BatteryVoltage": OncueSensor(
                name="BatteryVoltage",
                display_name="Battery Voltage",
                value="13.5",
                display_value="13.5 V",
                unit="V",
            ),
            "LubeOilTemperature": OncueSensor(
                name="LubeOilTemperature",
                display_name="Lube Oil Temperature",
                value=32,
                display_value="32 F",
                unit="F",
            ),
            "GensetControllerTemperature": OncueSensor(
                name="GensetControllerTemperature",
                display_name="Generator Controller Temperature",
                value=100.4,
                display_value="100.4 F",
                unit="F",
            ),
            "EngineCompartmentTemperature": OncueSensor(
                name="EngineCompartmentTemperature",
                display_name="Engine Compartment Temperature",
                value=84.2,
                display_value="84.2 F",
                unit="F",
            ),
            "GeneratorTrueTotalPower": OncueSensor(
                name="GeneratorTrueTotalPower",
                display_name="Generator True Total Power",
                value="0.0",
                display_value="0.0 W",
                unit="W",
            ),
            "GeneratorTruePercentOfRatedPower": OncueSensor(
                name="GeneratorTruePercentOfRatedPower",
                display_name="Generator True Percent Of Rated Power",
                value="0",
                display_value="0 %",
                unit="%",
            ),
            "GeneratorVoltageAverageLineToLine": OncueSensor(
                name="GeneratorVoltageAverageLineToLine",
                display_name="Generator Voltage Average Line To Line",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorFrequency": OncueSensor(
                name="GeneratorFrequency",
                display_name="Generator Frequency",
                value="0.0",
                display_value="0.0 Hz",
                unit="Hz",
            ),
            "GensetSerialNumber": OncueSensor(
                name="GensetSerialNumber",
                display_name="Generator Serial Number",
                value="33FDGMFR0026",
                display_value="33FDGMFR0026",
                unit=None,
            ),
            "GensetState": OncueSensor(
                name="GensetState",
                display_name="Generator State",
                value="Off",
                display_value="Off",
                unit=None,
            ),
            "GensetModelNumberSelect": OncueSensor(
                name="GensetModelNumberSelect",
                display_name="Genset Model Number Select",
                value="38 RCLB",
                display_value="38 RCLB",
                unit=None,
            ),
            "GensetControllerClockTime": OncueSensor(
                name="GensetControllerClockTime",
                display_name="Generator Controller Clock Time",
                value="2022-01-01 17:20:52",
                display_value="2022-01-01 17:20:52",
                unit=None,
            ),
            "GensetControllerTotalOperationTime": OncueSensor(
                name="GensetControllerTotalOperationTime",
                display_name="Generator Controller Total Operation Time",
                value="16482.0",
                display_value="16482.0 h",
                unit="h",
            ),
            "EngineTotalRunTime": OncueSensor(
                name="EngineTotalRunTime",
                display_name="Engine Total Run Time",
                value="28.1",
                display_value="28.1 h",
                unit="h",
            ),
            "AtsContactorPosition": OncueSensor(
                name="AtsContactorPosition",
                display_name="Ats Contactor Position",
                value="Source1",
                display_value="Source1",
                unit=None,
            ),
            "IPAddress": OncueSensor(
                name="IPAddress",
                display_name="IP Address",
                value="1.2.3.4:1026",
                display_value="1.2.3.4:1026",
                unit=None,
            ),
            "ConnectedServerIPAddress": OncueSensor(
                name="ConnectedServerIPAddress",
                display_name="Connected Server IP Address",
                value="40.117.195.28",
                display_value="40.117.195.28",
                unit=None,
            ),
            "NetworkConnectionEstablished": OncueSensor(
                name="NetworkConnectionEstablished",
                display_name="Network Connection Established",
                value="true",
                display_value="True",
                unit=None,
            ),
        },
    )
}


def _patch_login_and_data():
    @contextmanager
    def _patcher():
        with patch("homeassistant.components.oncue.Oncue.async_login",), patch(
            "homeassistant.components.oncue.Oncue.async_fetch_all",
            return_value=MOCK_ASYNC_FETCH_ALL,
        ):
            yield

    return _patcher()
