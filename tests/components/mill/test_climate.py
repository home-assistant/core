"""Tests for Mill climate."""

from unittest.mock import patch

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
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

HEATER_ID = "dev_id"
HEATER_NAME = "heater_name"
ENTITY_CLIMATE = f"climate.{HEATER_NAME}"

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
        # disable recorder behaviour
        patch(
            "homeassistant.components.mill.coordinator.MillHistoricDataUpdateCoordinator._async_update_data",
            return_value=None,
        ),
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
            "ambient_temperature": 20,
            "set_temperature": 20,
            "current_power": 0,
            "control_signal": 0,
            "raw_ambient_temperature": 19,
            "operation_mode": OperationMode.OFF.value,
        }
        milllocal.fetch_heater_and_sensor_data.return_value = status
        milllocal._status = status
        yield milllocal


## CLOUD HEATER INTEGRATION


@pytest.fixture
async def cloud_heater(hass: HomeAssistant, mock_mill) -> Heater:
    """Load Mill integration and creates one cloud heater."""

    heater = Heater(
        name=HEATER_NAME,
        device_id=HEATER_ID,
        available=True,
        is_heating=False,
        power_status=False,
        current_temp=20.0,
        set_temp=20.0,
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
async def cloud_heater_set_temp(mock_mill, cloud_heater):
    """Gets mock for the cloud heater `set_heater_temp` method."""
    return mock_mill.set_heater_temp


@pytest.fixture
async def cloud_heater_control(mock_mill, cloud_heater):
    """Gets mock for the cloud heater `heater_control` method."""
    return mock_mill.heater_control


@pytest.fixture
async def functional_cloud_heater(
    cloud_heater, cloud_heater_set_temp, cloud_heater_control
) -> Heater:
    """Make sure the cloud heater is "functional".

    This will create a pseudo-functional cloud heater, meaning that function calls will edit the original cloud heater in a similar way that the API would.
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
async def local_heater(hass: HomeAssistant, mock_mill_local) -> dict:
    """Local Mill Heater.

    This returns a by-reference status dict with which this heater's information is organised and updated.
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
async def local_heater_set_target_temperature(mock_mill_local, local_heater):
    """Gets mock for the local heater `set_target_temperature` method."""
    return mock_mill_local.set_target_temperature


@pytest.fixture
async def local_heater_set_mode_control_individually(mock_mill_local, local_heater):
    """Gets mock for the local heater `set_operation_mode_control_individually` method."""
    return mock_mill_local.set_operation_mode_control_individually


@pytest.fixture
async def local_heater_set_mode_off(mock_mill_local, local_heater):
    """Gets mock for the local heater `set_operation_mode_off` method."""
    return mock_mill_local.set_operation_mode_off


@pytest.fixture
async def functional_local_heater(
    mock_mill_local,
    local_heater_set_target_temperature,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
    local_heater,
) -> None:
    """Make sure the local heater is "functional".

    This will create a pseudo-functional local heater, meaning that function calls will edit the original local heater in a similar way that the API would.
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


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    functional_cloud_heater,
    cloud_heater_control,
) -> None:
    """Tests setting the HVAC mode HEAT."""

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    cloud_heater_control.assert_called_once_with(HEATER_ID, power_status=True)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.HEAT


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    cloud_heater_control,
) -> None:
    """Tests setting the HVAC mode OFF."""

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    cloud_heater_control.assert_called_once_with(HEATER_ID, power_status=False)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_set_bad_hvac_mode(
    hass: HomeAssistant,
    cloud_heater_control,
) -> None:
    """Tests setting the HVAC mode to an unsupported value."""

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    await hass.async_block_till_done()

    cloud_heater_control.assert_not_called()


async def test_set_temperature_hvac_heat(
    hass: HomeAssistant,
    functional_cloud_heater,
    cloud_heater_set_temp,
    cloud_heater_control,
) -> None:
    """Tests setting a temperature with HVAC mode HEAT."""

    temperature = 25

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_CLIMATE,
            ATTR_TEMPERATURE: temperature,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    cloud_heater_set_temp.assert_called_once_with(HEATER_ID, float(temperature))
    cloud_heater_control.assert_called_once_with(HEATER_ID, power_status=True)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


async def test_set_temperature_hvac_off(
    hass: HomeAssistant,
    functional_cloud_heater,
    cloud_heater_set_temp,
    cloud_heater_control,
) -> None:
    """Tests setting a temperature with HVAC mode OFF."""

    temperature = 25

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_CLIMATE,
            ATTR_TEMPERATURE: temperature,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    cloud_heater_set_temp.assert_called_once_with(HEATER_ID, float(temperature))
    cloud_heater_control.assert_called_once_with(HEATER_ID, power_status=False)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


async def test_set_temperature_no_hvac(
    hass: HomeAssistant,
    functional_cloud_heater,
    cloud_heater_set_temp,
    cloud_heater_control,
) -> None:
    """Tests setting a temperature with no HVAC mode."""

    temperature = 25

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_CLIMATE,
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    cloud_heater_set_temp.assert_called_once_with(HEATER_ID, float(temperature))
    cloud_heater_control.assert_not_called()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


async def test_set_temperature_bad_hvac(
    hass: HomeAssistant,
    functional_cloud_heater,
    cloud_heater_set_temp,
    cloud_heater_control,
) -> None:
    """Tests setting a temperature with a bad HVAC mode."""

    temperature = 25

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_CLIMATE,
                ATTR_TEMPERATURE: temperature,
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )

    await hass.async_block_till_done()

    # MillHeater will set the temperature before calling async_handle_set_hvac_mode,
    #   meaning an invalid HVAC mode will raise only after the temperature is set.
    cloud_heater_set_temp.assert_called_once_with(HEATER_ID, float(temperature))
    cloud_heater_control.assert_not_called()


### LOCAL


async def test_local_set_hvac_mode_heat(
    hass: HomeAssistant,
    functional_local_heater,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting a temperature with HVAC mode HEAT."""

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    local_heater_set_mode_control_individually.assert_called_once()
    local_heater_set_mode_off.assert_not_called()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.HEAT


async def test_local_set_hvac_mode_off(
    hass: HomeAssistant,
    functional_local_heater,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting a temperature with HVAC mode OFF."""

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    local_heater_set_mode_control_individually.assert_not_called()
    local_heater_set_mode_off.assert_called_once()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_local_set_bad_hvac_mode(
    hass: HomeAssistant,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting the HVAC mode to an unsupported value."""

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    await hass.async_block_till_done()

    local_heater_set_mode_control_individually.assert_not_called()
    local_heater_set_mode_off.assert_not_called()


async def test_local_set_temperature_hvac_heat(
    hass: HomeAssistant,
    functional_local_heater,
    local_heater_set_target_temperature,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting a temperature with HVAC mode HEAT."""

    temperature = 25

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_CLIMATE,
            ATTR_TEMPERATURE: temperature,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    local_heater_set_target_temperature.assert_called_once_with(float(temperature))
    local_heater_set_mode_control_individually.assert_called_once()
    local_heater_set_mode_off.assert_not_called()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


async def test_local_set_temperature_hvac_off(
    hass: HomeAssistant,
    functional_local_heater,
    local_heater_set_target_temperature,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting a temperature with HVAC mode OFF."""

    temperature = 25

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_CLIMATE,
            ATTR_TEMPERATURE: temperature,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    local_heater_set_target_temperature.assert_called_once_with(float(temperature))
    local_heater_set_mode_control_individually.assert_not_called()
    local_heater_set_mode_off.assert_called_once()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


async def test_local_set_temperature_no_hvac(
    hass: HomeAssistant,
    functional_local_heater,
    local_heater_set_target_temperature,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting a temperature with no HVAC mode."""

    temperature = 25

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_CLIMATE,
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    local_heater_set_target_temperature.assert_called_once_with(float(temperature))
    local_heater_set_mode_control_individually.assert_not_called()
    local_heater_set_mode_off.assert_not_called()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


async def test_local_set_temperature_bad_hvac(
    hass: HomeAssistant,
    functional_local_heater,
    local_heater_set_target_temperature,
    local_heater_set_mode_control_individually,
    local_heater_set_mode_off,
) -> None:
    """Tests locally setting a temperature with an unsupported HVAC mode."""

    temperature = 25

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_CLIMATE,
                ATTR_TEMPERATURE: temperature,
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )

    await hass.async_block_till_done()

    # LocalMillHeater will set the temperature before calling async_handle_set_hvac_mode,
    #   meaning an invalid HVAC mode will raise only after the temperature is set.
    local_heater_set_target_temperature.assert_called_once_with(float(temperature))
    local_heater_set_mode_control_individually.assert_not_called()
    local_heater_set_mode_off.assert_not_called()
