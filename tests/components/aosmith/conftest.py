"""Common fixtures for the A. O. Smith tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from py_aosmith import AOSmithAPIClient
from py_aosmith.models import (
    Device,
    DeviceStatus,
    DeviceType,
    EnergyUseData,
    EnergyUseHistoryEntry,
    OperationMode,
    SupportedOperationModeInfo,
)
import pytest

from homeassistant.components.aosmith.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, load_json_object_fixture

FIXTURE_USER_INPUT = {
    CONF_EMAIL: "testemail@example.com",
    CONF_PASSWORD: "test-password",
}


def build_device_fixture(
    heat_pump: bool, mode_pending: bool, setpoint_pending: bool, has_vacation_mode: bool
):
    """Build a fixture for a device."""
    supported_modes: list[SupportedOperationModeInfo] = [
        SupportedOperationModeInfo(
            mode=OperationMode.ELECTRIC,
            original_name="ELECTRIC",
            has_day_selection=True,
        ),
    ]

    if heat_pump:
        supported_modes.append(
            SupportedOperationModeInfo(
                mode=OperationMode.HYBRID,
                original_name="HYBRID",
                has_day_selection=False,
            )
        )
        supported_modes.append(
            SupportedOperationModeInfo(
                mode=OperationMode.HEAT_PUMP,
                original_name="HEAT_PUMP",
                has_day_selection=False,
            )
        )

    if has_vacation_mode:
        supported_modes.append(
            SupportedOperationModeInfo(
                mode=OperationMode.VACATION,
                original_name="VACATION",
                has_day_selection=True,
            )
        )

    device_type = (
        DeviceType.NEXT_GEN_HEAT_PUMP if heat_pump else DeviceType.RE3_CONNECTED
    )

    current_mode = OperationMode.HEAT_PUMP if heat_pump else OperationMode.ELECTRIC

    model = "HPTS-50 200 202172000" if heat_pump else "EE12-50H55DVF 100,3806368"

    return Device(
        brand="aosmith",
        model=model,
        device_type=device_type,
        dsn="dsn",
        junction_id="junctionId",
        name="My water heater",
        serial="serial",
        install_location="Basement",
        supported_modes=supported_modes,
        status=DeviceStatus(
            firmware_version="2.14",
            is_online=True,
            current_mode=current_mode,
            mode_change_pending=mode_pending,
            temperature_setpoint=130,
            temperature_setpoint_pending=setpoint_pending,
            temperature_setpoint_previous=130,
            temperature_setpoint_maximum=130,
            hot_water_status=90,
        ),
    )


ENERGY_USE_FIXTURE = EnergyUseData(
    lifetime_kwh=132.825,
    history=[
        EnergyUseHistoryEntry(
            date="2023-10-30T04:00:00.000Z",
            energy_use_kwh=2.01,
        ),
        EnergyUseHistoryEntry(
            date="2023-10-31T04:00:00.000Z",
            energy_use_kwh=1.542,
        ),
        EnergyUseHistoryEntry(
            date="2023-11-01T04:00:00.000Z",
            energy_use_kwh=1.908,
        ),
    ],
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
        unique_id=FIXTURE_USER_INPUT[CONF_EMAIL],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aosmith.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def get_devices_fixture_heat_pump() -> bool:
    """Return whether the device in the get_devices fixture should be a heat pump water heater."""
    return True


@pytest.fixture
def get_devices_fixture_mode_pending() -> bool:
    """Return whether to set mode_pending in the get_devices fixture."""
    return False


@pytest.fixture
def get_devices_fixture_setpoint_pending() -> bool:
    """Return whether to set setpoint_pending in the get_devices fixture."""
    return False


@pytest.fixture
def get_devices_fixture_has_vacation_mode() -> bool:
    """Return whether to include vacation mode in the get_devices fixture."""
    return True


@pytest.fixture
async def mock_client(
    get_devices_fixture_heat_pump: bool,
    get_devices_fixture_mode_pending: bool,
    get_devices_fixture_setpoint_pending: bool,
    get_devices_fixture_has_vacation_mode: bool,
) -> Generator[MagicMock]:
    """Return a mocked client."""
    get_devices_fixture = [
        build_device_fixture(
            heat_pump=get_devices_fixture_heat_pump,
            mode_pending=get_devices_fixture_mode_pending,
            setpoint_pending=get_devices_fixture_setpoint_pending,
            has_vacation_mode=get_devices_fixture_has_vacation_mode,
        )
    ]
    get_all_device_info_fixture = load_json_object_fixture(
        "get_all_device_info.json", DOMAIN
    )

    client_mock = MagicMock(AOSmithAPIClient)
    client_mock.get_devices = AsyncMock(return_value=get_devices_fixture)
    client_mock.get_energy_use_data = AsyncMock(return_value=ENERGY_USE_FIXTURE)
    client_mock.get_all_device_info = AsyncMock(
        return_value=get_all_device_info_fixture
    )

    return client_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    with patch(
        "homeassistant.components.aosmith.AOSmithAPIClient", return_value=mock_client
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry
