"""Tests for the Oncue integration."""

from contextlib import contextmanager
from unittest.mock import patch

from aiooncue import LoginFailedException, OncueDevice, OncueSensor

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
            "EngineTargetSpeed": OncueSensor(
                name="EngineTargetSpeed",
                display_name="Engine Target Speed",
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
                value="13.4",
                display_value="13.4 V",
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
                value=84.2,
                display_value="84.2 F",
                unit="F",
            ),
            "EngineCompartmentTemperature": OncueSensor(
                name="EngineCompartmentTemperature",
                display_name="Engine Compartment Temperature",
                value=62.6,
                display_value="62.6 F",
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
            "GeneratorVoltageAB": OncueSensor(
                name="GeneratorVoltageAB",
                display_name="Generator Voltage AB",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorVoltageAverageLineToLine": OncueSensor(
                name="GeneratorVoltageAverageLineToLine",
                display_name="Generator Voltage Average Line To Line",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorCurrentAverage": OncueSensor(
                name="GeneratorCurrentAverage",
                display_name="Generator Current Average",
                value="0.0",
                display_value="0.0 A",
                unit="A",
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
            "GensetControllerSerialNumber": OncueSensor(
                name="GensetControllerSerialNumber",
                display_name="Generator Controller Serial Number",
                value="-1",
                display_value="-1",
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
                value="2022-01-13 18:08:13",
                display_value="2022-01-13 18:08:13",
                unit=None,
            ),
            "GensetControllerTotalOperationTime": OncueSensor(
                name="GensetControllerTotalOperationTime",
                display_name="Generator Controller Total Operation Time",
                value="16770.8",
                display_value="16770.8 h",
                unit="h",
            ),
            "EngineTotalRunTime": OncueSensor(
                name="EngineTotalRunTime",
                display_name="Engine Total Run Time",
                value="28.1",
                display_value="28.1 h",
                unit="h",
            ),
            "EngineTotalRunTimeLoaded": OncueSensor(
                name="EngineTotalRunTimeLoaded",
                display_name="Engine Total Run Time Loaded",
                value="5.5",
                display_value="5.5 h",
                unit="h",
            ),
            "EngineTotalNumberOfStarts": OncueSensor(
                name="EngineTotalNumberOfStarts",
                display_name="Engine Total Number Of Starts",
                value="101",
                display_value="101",
                unit=None,
            ),
            "GensetTotalEnergy": OncueSensor(
                name="GensetTotalEnergy",
                display_name="Genset Total Energy",
                value="1.2022309E7",
                display_value="1.2022309E7 kWh",
                unit="kWh",
            ),
            "AtsContactorPosition": OncueSensor(
                name="AtsContactorPosition",
                display_name="Ats Contactor Position",
                value="Source1",
                display_value="Source1",
                unit=None,
            ),
            "AtsSourcesAvailable": OncueSensor(
                name="AtsSourcesAvailable",
                display_name="Ats Sources Available",
                value="Source1",
                display_value="Source1",
                unit=None,
            ),
            "Source1VoltageAverageLineToLine": OncueSensor(
                name="Source1VoltageAverageLineToLine",
                display_name="Source1 Voltage Average Line To Line",
                value="253.5",
                display_value="253.5 V",
                unit="V",
            ),
            "Source2VoltageAverageLineToLine": OncueSensor(
                name="Source2VoltageAverageLineToLine",
                display_name="Source2 Voltage Average Line To Line",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "IPAddress": OncueSensor(
                name="IPAddress",
                display_name="IP Address",
                value="1.2.3.4:1026",
                display_value="1.2.3.4:1026",
                unit=None,
            ),
            "MacAddress": OncueSensor(
                name="MacAddress",
                display_name="Mac Address",
                value="221157033710592",
                display_value="221157033710592",
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
            "SerialNumber": OncueSensor(
                name="SerialNumber",
                display_name="Serial Number",
                value="1073879692",
                display_value="1073879692",
                unit=None,
            ),
        },
    )
}


MOCK_ASYNC_FETCH_ALL_OFFLINE_DEVICE = {
    "456789": OncueDevice(
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
            "EngineTargetSpeed": OncueSensor(
                name="EngineTargetSpeed",
                display_name="Engine Target Speed",
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
                value="13.4",
                display_value="13.4 V",
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
                value=84.2,
                display_value="84.2 F",
                unit="F",
            ),
            "EngineCompartmentTemperature": OncueSensor(
                name="EngineCompartmentTemperature",
                display_name="Engine Compartment Temperature",
                value=62.6,
                display_value="62.6 F",
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
            "GeneratorVoltageAB": OncueSensor(
                name="GeneratorVoltageAB",
                display_name="Generator Voltage AB",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorVoltageAverageLineToLine": OncueSensor(
                name="GeneratorVoltageAverageLineToLine",
                display_name="Generator Voltage Average Line To Line",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorCurrentAverage": OncueSensor(
                name="GeneratorCurrentAverage",
                display_name="Generator Current Average",
                value="0.0",
                display_value="0.0 A",
                unit="A",
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
            "GensetControllerSerialNumber": OncueSensor(
                name="GensetControllerSerialNumber",
                display_name="Generator Controller Serial Number",
                value="-1",
                display_value="-1",
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
                value="2022-01-13 18:08:13",
                display_value="2022-01-13 18:08:13",
                unit=None,
            ),
            "GensetControllerTotalOperationTime": OncueSensor(
                name="GensetControllerTotalOperationTime",
                display_name="Generator Controller Total Operation Time",
                value="16770.8",
                display_value="16770.8 h",
                unit="h",
            ),
            "EngineTotalRunTime": OncueSensor(
                name="EngineTotalRunTime",
                display_name="Engine Total Run Time",
                value="28.1",
                display_value="28.1 h",
                unit="h",
            ),
            "EngineTotalRunTimeLoaded": OncueSensor(
                name="EngineTotalRunTimeLoaded",
                display_name="Engine Total Run Time Loaded",
                value="5.5",
                display_value="5.5 h",
                unit="h",
            ),
            "EngineTotalNumberOfStarts": OncueSensor(
                name="EngineTotalNumberOfStarts",
                display_name="Engine Total Number Of Starts",
                value="101",
                display_value="101",
                unit=None,
            ),
            "GensetTotalEnergy": OncueSensor(
                name="GensetTotalEnergy",
                display_name="Genset Total Energy",
                value="1.2022309E7",
                display_value="1.2022309E7 kWh",
                unit="kWh",
            ),
            "AtsContactorPosition": OncueSensor(
                name="AtsContactorPosition",
                display_name="Ats Contactor Position",
                value="Source1",
                display_value="Source1",
                unit=None,
            ),
            "AtsSourcesAvailable": OncueSensor(
                name="AtsSourcesAvailable",
                display_name="Ats Sources Available",
                value="Source1",
                display_value="Source1",
                unit=None,
            ),
            "Source1VoltageAverageLineToLine": OncueSensor(
                name="Source1VoltageAverageLineToLine",
                display_name="Source1 Voltage Average Line To Line",
                value="253.5",
                display_value="253.5 V",
                unit="V",
            ),
            "Source2VoltageAverageLineToLine": OncueSensor(
                name="Source2VoltageAverageLineToLine",
                display_name="Source2 Voltage Average Line To Line",
                value="0.0",
                display_value="0.0 V",
                unit="V",
            ),
            "IPAddress": OncueSensor(
                name="IPAddress",
                display_name="IP Address",
                value="1.2.3.4:1026",
                display_value="1.2.3.4:1026",
                unit=None,
            ),
            "MacAddress": OncueSensor(
                name="MacAddress",
                display_name="Mac Address",
                value="--",
                display_value="--",
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
            "SerialNumber": OncueSensor(
                name="SerialNumber",
                display_name="Serial Number",
                value="1073879692",
                display_value="1073879692",
                unit=None,
            ),
        },
    )
}

MOCK_ASYNC_FETCH_ALL_UNAVAILABLE_DEVICE = {
    "456789": OncueDevice(
        name="My Generator",
        state="Off",
        product_name="RDC 2.4",
        hardware_version="319",
        serial_number="SERIAL",
        sensors={
            "Product": OncueSensor(
                name="Product",
                display_name="Controller Type",
                value="--",
                display_value="RDC 2.4",
                unit=None,
            ),
            "FirmwareVersion": OncueSensor(
                name="FirmwareVersion",
                display_name="Current Firmware",
                value="--",
                display_value="2.0.6",
                unit=None,
            ),
            "LatestFirmware": OncueSensor(
                name="LatestFirmware",
                display_name="Latest Firmware",
                value="--",
                display_value="2.0.6",
                unit=None,
            ),
            "EngineSpeed": OncueSensor(
                name="EngineSpeed",
                display_name="Engine Speed",
                value="--",
                display_value="0 R/min",
                unit="R/min",
            ),
            "EngineTargetSpeed": OncueSensor(
                name="EngineTargetSpeed",
                display_name="Engine Target Speed",
                value="--",
                display_value="0 R/min",
                unit="R/min",
            ),
            "EngineOilPressure": OncueSensor(
                name="EngineOilPressure",
                display_name="Engine Oil Pressure",
                value="--",
                display_value="0 Psi",
                unit="Psi",
            ),
            "EngineCoolantTemperature": OncueSensor(
                name="EngineCoolantTemperature",
                display_name="Engine Coolant Temperature",
                value="--",
                display_value="32 F",
                unit="F",
            ),
            "BatteryVoltage": OncueSensor(
                name="BatteryVoltage",
                display_name="Battery Voltage",
                value="0.0",
                display_value="13.4 V",
                unit="V",
            ),
            "LubeOilTemperature": OncueSensor(
                name="LubeOilTemperature",
                display_name="Lube Oil Temperature",
                value="--",
                display_value="32 F",
                unit="F",
            ),
            "GensetControllerTemperature": OncueSensor(
                name="GensetControllerTemperature",
                display_name="Generator Controller Temperature",
                value="--",
                display_value="84.2 F",
                unit="F",
            ),
            "EngineCompartmentTemperature": OncueSensor(
                name="EngineCompartmentTemperature",
                display_name="Engine Compartment Temperature",
                value="--",
                display_value="62.6 F",
                unit="F",
            ),
            "GeneratorTrueTotalPower": OncueSensor(
                name="GeneratorTrueTotalPower",
                display_name="Generator True Total Power",
                value="--",
                display_value="0.0 W",
                unit="W",
            ),
            "GeneratorTruePercentOfRatedPower": OncueSensor(
                name="GeneratorTruePercentOfRatedPower",
                display_name="Generator True Percent Of Rated Power",
                value="--",
                display_value="0 %",
                unit="%",
            ),
            "GeneratorVoltageAB": OncueSensor(
                name="GeneratorVoltageAB",
                display_name="Generator Voltage AB",
                value="--",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorVoltageAverageLineToLine": OncueSensor(
                name="GeneratorVoltageAverageLineToLine",
                display_name="Generator Voltage Average Line To Line",
                value="--",
                display_value="0.0 V",
                unit="V",
            ),
            "GeneratorCurrentAverage": OncueSensor(
                name="GeneratorCurrentAverage",
                display_name="Generator Current Average",
                value="--",
                display_value="0.0 A",
                unit="A",
            ),
            "GeneratorFrequency": OncueSensor(
                name="GeneratorFrequency",
                display_name="Generator Frequency",
                value="--",
                display_value="0.0 Hz",
                unit="Hz",
            ),
            "GensetSerialNumber": OncueSensor(
                name="GensetSerialNumber",
                display_name="Generator Serial Number",
                value="--",
                display_value="33FDGMFR0026",
                unit=None,
            ),
            "GensetState": OncueSensor(
                name="GensetState",
                display_name="Generator State",
                value="--",
                display_value="Off",
                unit=None,
            ),
            "GensetControllerSerialNumber": OncueSensor(
                name="GensetControllerSerialNumber",
                display_name="Generator Controller Serial Number",
                value="--",
                display_value="-1",
                unit=None,
            ),
            "GensetModelNumberSelect": OncueSensor(
                name="GensetModelNumberSelect",
                display_name="Genset Model Number Select",
                value="--",
                display_value="38 RCLB",
                unit=None,
            ),
            "GensetControllerClockTime": OncueSensor(
                name="GensetControllerClockTime",
                display_name="Generator Controller Clock Time",
                value="--",
                display_value="2022-01-13 18:08:13",
                unit=None,
            ),
            "GensetControllerTotalOperationTime": OncueSensor(
                name="GensetControllerTotalOperationTime",
                display_name="Generator Controller Total Operation Time",
                value="--",
                display_value="16770.8 h",
                unit="h",
            ),
            "EngineTotalRunTime": OncueSensor(
                name="EngineTotalRunTime",
                display_name="Engine Total Run Time",
                value="--",
                display_value="28.1 h",
                unit="h",
            ),
            "EngineTotalRunTimeLoaded": OncueSensor(
                name="EngineTotalRunTimeLoaded",
                display_name="Engine Total Run Time Loaded",
                value="--",
                display_value="5.5 h",
                unit="h",
            ),
            "EngineTotalNumberOfStarts": OncueSensor(
                name="EngineTotalNumberOfStarts",
                display_name="Engine Total Number Of Starts",
                value="--",
                display_value="101",
                unit=None,
            ),
            "GensetTotalEnergy": OncueSensor(
                name="GensetTotalEnergy",
                display_name="Genset Total Energy",
                value="--",
                display_value="1.2022309E7 kWh",
                unit="kWh",
            ),
            "AtsContactorPosition": OncueSensor(
                name="AtsContactorPosition",
                display_name="Ats Contactor Position",
                value="--",
                display_value="Source1",
                unit=None,
            ),
            "AtsSourcesAvailable": OncueSensor(
                name="AtsSourcesAvailable",
                display_name="Ats Sources Available",
                value="--",
                display_value="Source1",
                unit=None,
            ),
            "Source1VoltageAverageLineToLine": OncueSensor(
                name="Source1VoltageAverageLineToLine",
                display_name="Source1 Voltage Average Line To Line",
                value="--",
                display_value="253.5 V",
                unit="V",
            ),
            "Source2VoltageAverageLineToLine": OncueSensor(
                name="Source2VoltageAverageLineToLine",
                display_name="Source2 Voltage Average Line To Line",
                value="--",
                display_value="0.0 V",
                unit="V",
            ),
            "IPAddress": OncueSensor(
                name="IPAddress",
                display_name="IP Address",
                value="--",
                display_value="1.2.3.4:1026",
                unit=None,
            ),
            "MacAddress": OncueSensor(
                name="MacAddress",
                display_name="Mac Address",
                value="--",
                display_value="--",
                unit=None,
            ),
            "ConnectedServerIPAddress": OncueSensor(
                name="ConnectedServerIPAddress",
                display_name="Connected Server IP Address",
                value="--",
                display_value="40.117.195.28",
                unit=None,
            ),
            "NetworkConnectionEstablished": OncueSensor(
                name="NetworkConnectionEstablished",
                display_name="Network Connection Established",
                value="--",
                display_value="True",
                unit=None,
            ),
            "SerialNumber": OncueSensor(
                name="SerialNumber",
                display_name="Serial Number",
                value="--",
                display_value="1073879692",
                unit=None,
            ),
        },
    )
}


def _patch_login_and_data():
    @contextmanager
    def _patcher():
        with (
            patch(
                "homeassistant.components.oncue.Oncue.async_login",
            ),
            patch(
                "homeassistant.components.oncue.Oncue.async_fetch_all",
                return_value=MOCK_ASYNC_FETCH_ALL,
            ),
        ):
            yield

    return _patcher()


def _patch_login_and_data_offline_device():
    @contextmanager
    def _patcher():
        with (
            patch(
                "homeassistant.components.oncue.Oncue.async_login",
            ),
            patch(
                "homeassistant.components.oncue.Oncue.async_fetch_all",
                return_value=MOCK_ASYNC_FETCH_ALL_OFFLINE_DEVICE,
            ),
        ):
            yield

    return _patcher()


def _patch_login_and_data_unavailable():
    @contextmanager
    def _patcher():
        with (
            patch("homeassistant.components.oncue.Oncue.async_login"),
            patch(
                "homeassistant.components.oncue.Oncue.async_fetch_all",
                return_value=MOCK_ASYNC_FETCH_ALL_UNAVAILABLE_DEVICE,
            ),
        ):
            yield

    return _patcher()


def _patch_login_and_data_unavailable_device():
    @contextmanager
    def _patcher():
        with (
            patch("homeassistant.components.oncue.Oncue.async_login"),
            patch(
                "homeassistant.components.oncue.Oncue.async_fetch_all",
                return_value=MOCK_ASYNC_FETCH_ALL_UNAVAILABLE_DEVICE,
            ),
        ):
            yield

    return _patcher()


def _patch_login_and_data_auth_failure():
    @contextmanager
    def _patcher():
        with (
            patch(
                "homeassistant.components.oncue.Oncue.async_login",
                side_effect=LoginFailedException,
            ),
            patch(
                "homeassistant.components.oncue.Oncue.async_fetch_all",
                side_effect=LoginFailedException,
            ),
        ):
            yield

    return _patcher()
