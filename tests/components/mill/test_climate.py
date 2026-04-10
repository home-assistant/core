"""Tests for Mill climate."""

import contextlib
from contextlib import nullcontext
from unittest.mock import MagicMock, call, patch

from mill import Heater
from mill_local import OperationMode
import pytest

from homeassistant.components import mill
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.mill.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

HEATER_ID = "dev_id"
HEATER_NAME = "heater_name"
ENTITY_CLIMATE = f"climate.{HEATER_NAME}"

TEST_SET_TEMPERATURE = 25
TEST_AMBIENT_TEMPERATURE = 20

NULL_EFFECT = nullcontext()

## MILL AND LOCAL MILL FIXTURES


@pytest.fixture
async def mock_mill():
    """Mock the mill.Mill object.

    It is imported and initialized only in /homeassistant/components/mill/__init__.py
    """

    with (
        patch(
            "homeassistant.components.mill.Mill",
            autospec=True,
        ) as mock_mill_class,
    ):
        mill = mock_mill_class.return_value
        mill.connect.return_value = True
        mill.fetch_heater_and_sensor_data.return_value = {}
        mill.fetch_historic_energy_usage.return_value = {}
        yield mill


@pytest.fixture
async def mock_mill_local():
    """Mock the mill_local.Mill object."""

    with (
        patch(
            "homeassistant.components.mill.MillLocal",
            autospec=True,
        ) as mock_mill_local_class,
    ):
        milllocal = mock_mill_local_class.return_value
        milllocal.url = "http://dummy.url"
        milllocal.name = HEATER_NAME
        milllocal.mac_address = "dead:beef"
        milllocal.version = "0x210927"
        milllocal.connect.return_value = {
            "name": milllocal.name,
            "mac_address": milllocal.mac_address,
            "version": milllocal.version,
            "operation_key": "",
            "status": "ok",
        }
        status = {
            "ambient_temperature": TEST_AMBIENT_TEMPERATURE,
            "set_temperature": TEST_AMBIENT_TEMPERATURE,
            "current_power": 0,
            "control_signal": 0,
            "raw_ambient_temperature": TEST_AMBIENT_TEMPERATURE,
            "operation_mode": OperationMode.OFF.value,
        }
        milllocal.fetch_heater_and_sensor_data.return_value = status
        milllocal._status = status
        yield milllocal


## CLOUD HEATER INTEGRATION


@pytest.fixture
async def cloud_heater(hass: HomeAssistant, mock_mill: MagicMock) -> Heater:
    """Load Mill integration and creates one cloud heater."""

    heater = Heater(
        name=HEATER_NAME,
        device_id=HEATER_ID,
        available=True,
        is_heating=False,
        power_status=False,
        current_temp=float(TEST_AMBIENT_TEMPERATURE),
        set_temp=float(TEST_AMBIENT_TEMPERATURE),
    )

    devices = {HEATER_ID: heater}

    mock_mill.fetch_heater_and_sensor_data.return_value = devices
    mock_mill.devices = devices

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    config_entry.add_to_hass(hass)

    # We just need to load the climate component.
    with patch("homeassistant.components.mill.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    return heater


@pytest.fixture
async def cloud_heater_set_temp(mock_mill: MagicMock, cloud_heater: MagicMock):
    """Gets mock for the cloud heater `set_heater_temp` method."""
    return mock_mill.set_heater_temp


@pytest.fixture
async def cloud_heater_control(mock_mill: MagicMock, cloud_heater: MagicMock):
    """Gets mock for the cloud heater `heater_control` method."""
    return mock_mill.heater_control


@pytest.fixture
async def functional_cloud_heater(
    cloud_heater: MagicMock,
    cloud_heater_set_temp: MagicMock,
    cloud_heater_control: MagicMock,
) -> Heater:
    """Make sure the cloud heater is "functional".

    This will create a pseudo-functional cloud heater,
    meaning that function calls will edit the original cloud heater
    in a similar way that the API would.
    """

    def calculate_heating():
        if (
            cloud_heater.power_status
            and cloud_heater.set_temp > cloud_heater.current_temp
        ):
            cloud_heater.is_heating = True

    def set_temperature(device_id: str, set_temp: float):
        assert device_id == HEATER_ID, "set_temperature called with wrong device_id"

        cloud_heater.set_temp = set_temp

        calculate_heating()

    def heater_control(device_id: str, power_status: bool):
        assert device_id == HEATER_ID, "set_temperature called with wrong device_id"

        # power_status gives the "do we want to heat, Y/N", while is_heating is based on temperature and internal state and whatnot.
        cloud_heater.power_status = power_status

        calculate_heating()

    cloud_heater_set_temp.side_effect = set_temperature
    cloud_heater_control.side_effect = heater_control

    return cloud_heater


## LOCAL HEATER INTEGRATION


@pytest.fixture
async def local_heater(hass: HomeAssistant, mock_mill_local: MagicMock) -> dict:
    """Local Mill Heater.

    This returns a by-reference status dict
    with which this heater's information is organised and updated.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            mill.CONF_IP_ADDRESS: "192.168.1.59",
            mill.CONNECTION_TYPE: mill.LOCAL,
        },
    )
    config_entry.add_to_hass(hass)

    # We just need to load the climate component.
    with patch("homeassistant.components.mill.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    return mock_mill_local._status


@pytest.fixture
async def local_heater_set_target_temperature(
    mock_mill_local: MagicMock, local_heater: MagicMock
):
    """Gets mock for the local heater `set_target_temperature` method."""
    return mock_mill_local.set_target_temperature


@pytest.fixture
async def local_heater_set_mode_control_individually(
    mock_mill_local: MagicMock, local_heater: MagicMock
):
    """Gets mock for the local heater `set_operation_mode_control_individually` method."""
    return mock_mill_local.set_operation_mode_control_individually


@pytest.fixture
async def local_heater_set_mode_off(
    mock_mill_local: MagicMock, local_heater: MagicMock
):
    """Gets mock for the local heater `set_operation_mode_off` method."""
    return mock_mill_local.set_operation_mode_off


@pytest.fixture
async def functional_local_heater(
    mock_mill_local: MagicMock,
    local_heater_set_target_temperature: MagicMock,
    local_heater_set_mode_control_individually: MagicMock,
    local_heater_set_mode_off: MagicMock,
    local_heater: MagicMock,
) -> None:
    """Make sure the local heater is "functional".

    This will create a pseudo-functional local heater,
    meaning that function calls will edit the original local heater
    in a similar way that the API would.
    """

    def set_temperature(target_temperature: float):
        local_heater["set_temperature"] = target_temperature

    def set_operation_mode(operation_mode: OperationMode):
        local_heater["operation_mode"] = operation_mode.value

    def mode_control_individually():
        set_operation_mode(OperationMode.CONTROL_INDIVIDUALLY)

    def mode_off():
        set_operation_mode(OperationMode.OFF)

    local_heater_set_target_temperature.side_effect = set_temperature
    local_heater_set_mode_control_individually.side_effect = mode_control_individually
    local_heater_set_mode_off.side_effect = mode_off


### CLOUD


@pytest.mark.parametrize(
    (
        "before_state",
        "before_attrs",
        "service_name",
        "service_params",
        "effect",
        "heater_control_calls",
        "heater_set_temp_calls",
        "after_state",
        "after_attrs",
    ),
    [
        # set_hvac_mode
        (
            HVACMode.OFF,
            {},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            NULL_EFFECT,
            [call(HEATER_ID, power_status=True)],
            [],
            HVACMode.HEAT,
            {},
        ),
        (
            HVACMode.OFF,
            {},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            NULL_EFFECT,
            [call(HEATER_ID, power_status=False)],
            [],
            HVACMode.OFF,
            {},
        ),
        (
            HVACMode.OFF,
            {},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            pytest.raises(HomeAssistantError),
            [],
            [],
            HVACMode.OFF,
            {},
        ),
        # set_temperature (with hvac mode)
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE, ATTR_HVAC_MODE: HVACMode.HEAT},
            NULL_EFFECT,
            [call(HEATER_ID, power_status=True)],
            [call(HEATER_ID, float(TEST_SET_TEMPERATURE))],
            HVACMode.HEAT,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
        ),
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE, ATTR_HVAC_MODE: HVACMode.OFF},
            NULL_EFFECT,
            [call(HEATER_ID, power_status=False)],
            [call(HEATER_ID, float(TEST_SET_TEMPERATURE))],
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
        ),
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
            NULL_EFFECT,
            [],
            [call(HEATER_ID, float(TEST_SET_TEMPERATURE))],
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
        ),
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE, ATTR_HVAC_MODE: HVACMode.COOL},
            pytest.raises(HomeAssistantError),
            # MillHeater will set the temperature before calling async_handle_set_hvac_mode,
            #   meaning an invalid HVAC mode will raise only after the temperature is set.
            [],
            [call(HEATER_ID, float(TEST_SET_TEMPERATURE))],
            HVACMode.OFF,
            # likewise, in this test, it hasn't had the chance to update its ambient temperature,
            # because the exception is raised before a refresh can be requested from the coordinator
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
        ),
    ],
)
async def test_cloud_heater(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    functional_cloud_heater: MagicMock,
    cloud_heater_control: MagicMock,
    cloud_heater_set_temp: MagicMock,
    before_state: HVACMode,
    before_attrs: dict,
    service_name: str,
    service_params: dict,
    effect: contextlib.AbstractContextManager,
    heater_control_calls: list,
    heater_set_temp_calls: list,
    after_state: HVACMode,
    after_attrs: dict,
) -> None:
    """Tests setting HVAC mode (directly or through set_temperature) for a cloud heater."""

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == before_state
    for attr, value in before_attrs.items():
        assert state.attributes.get(attr) == value

    with effect:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service_name,
            service_params | {ATTR_ENTITY_ID: ENTITY_CLIMATE},
            blocking=True,
        )

    await hass.async_block_till_done()

    cloud_heater_control.assert_has_calls(heater_control_calls)
    cloud_heater_set_temp.assert_has_calls(heater_set_temp_calls)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == after_state
    for attr, value in after_attrs.items():
        assert state.attributes.get(attr) == value


### LOCAL


@pytest.mark.parametrize(
    (
        "before_state",
        "before_attrs",
        "service_name",
        "service_params",
        "effect",
        "heater_mode_set_individually_calls",
        "heater_mode_set_off_calls",
        "heater_set_target_temperature_calls",
        "after_state",
        "after_attrs",
    ),
    [
        # set_hvac_mode
        (
            HVACMode.OFF,
            {},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            NULL_EFFECT,
            [call()],
            [],
            [],
            HVACMode.HEAT,
            {},
        ),
        (
            HVACMode.OFF,
            {},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            NULL_EFFECT,
            [],
            [call()],
            [],
            HVACMode.OFF,
            {},
        ),
        (
            HVACMode.OFF,
            {},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            pytest.raises(HomeAssistantError),
            [],
            [],
            [],
            HVACMode.OFF,
            {},
        ),
        # set_temperature (with hvac mode)
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE, ATTR_HVAC_MODE: HVACMode.HEAT},
            NULL_EFFECT,
            [call()],
            [],
            [call(float(TEST_SET_TEMPERATURE))],
            HVACMode.HEAT,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
        ),
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE, ATTR_HVAC_MODE: HVACMode.OFF},
            NULL_EFFECT,
            [],
            [call()],
            [call(float(TEST_SET_TEMPERATURE))],
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
        ),
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
            NULL_EFFECT,
            [],
            [],
            [call(float(TEST_SET_TEMPERATURE))],
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE},
        ),
        (
            HVACMode.OFF,
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: TEST_SET_TEMPERATURE, ATTR_HVAC_MODE: HVACMode.COOL},
            pytest.raises(HomeAssistantError),
            # LocalMillHeater will set the temperature before calling async_handle_set_hvac_mode,
            #   meaning an invalid HVAC mode will raise only after the temperature is set.
            [],
            [],
            [call(float(TEST_SET_TEMPERATURE))],
            HVACMode.OFF,
            # likewise, in this test, it hasn't had the chance to update its ambient temperature,
            # because the exception is raised before a refresh can be requested from the coordinator
            {ATTR_TEMPERATURE: TEST_AMBIENT_TEMPERATURE},
        ),
    ],
)
async def test_local_heater(
    hass: HomeAssistant,
    functional_local_heater: MagicMock,
    local_heater_set_mode_control_individually: MagicMock,
    local_heater_set_mode_off: MagicMock,
    local_heater_set_target_temperature: MagicMock,
    before_state: HVACMode,
    before_attrs: dict,
    service_name: str,
    service_params: dict,
    effect: contextlib.AbstractContextManager,
    heater_mode_set_individually_calls: list,
    heater_mode_set_off_calls: list,
    heater_set_target_temperature_calls: list,
    after_state: HVACMode,
    after_attrs: dict,
) -> None:
    """Tests setting HVAC mode (directly or through set_temperature) for a local heater."""

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == before_state
    for attr, value in before_attrs.items():
        assert state.attributes.get(attr) == value

    with effect:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service_name,
            service_params | {ATTR_ENTITY_ID: ENTITY_CLIMATE},
            blocking=True,
        )
    await hass.async_block_till_done()

    local_heater_set_mode_control_individually.assert_has_calls(
        heater_mode_set_individually_calls
    )
    local_heater_set_mode_off.assert_has_calls(heater_mode_set_off_calls)
    local_heater_set_target_temperature.assert_has_calls(
        heater_set_target_temperature_calls
    )

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == after_state
    for attr, value in after_attrs.items():
        assert state.attributes.get(attr) == value
