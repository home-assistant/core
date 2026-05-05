"""Common fixtures for the Ouman EH-800 tests."""

from collections.abc import Generator
from contextlib import nullcontext
from unittest.mock import AsyncMock, patch

from ouman_eh_800_api import (
    L1BaseEndpoints,
    L1RoomSensor,
    OumanEndpoint,
    OumanRegistrySet,
    OumanValues,
    SystemEndpoints,
)
import pytest

from homeassistant.components.ouman_eh_800.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_URL = "http://192.168.1.100"
TEST_USERNAME = "test-user"
TEST_PASSWORD = "test-pass"

_REGISTRY_SET = OumanRegistrySet(
    registries=[SystemEndpoints, L1BaseEndpoints, L1RoomSensor],
)

_MOCK_VALUES: dict[OumanEndpoint, OumanValues] = {
    SystemEndpoints.OUTSIDE_TEMPERATURE: -5.2,
    SystemEndpoints.RELAY_CONFIGURATION_TYPE: "",
    SystemEndpoints.RELAY_STATUS_TEXT: "Rele ei käytössä",
    SystemEndpoints.L2_INSTALLED_STATUS: "0",
    L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE: 45.3,
    L1BaseEndpoints.VALVE_POSITION: 50.0,
    L1BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE: 45.0,
    L1BaseEndpoints.FINE_ADJUSTMENT_EFFECT: 0.5,
    L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE_SETPOINT: 45.0,
    L1BaseEndpoints.TEMPERATURE_LEVEL_STATUS_TEXT: "L1 Normaalilämpö",
    L1BaseEndpoints.CIRCUIT_NAME: "Patterilämmitys",
    L1BaseEndpoints.ROOM_SENSOR_INSTALLED: "on",
    L1RoomSensor.ROOM_TEMPERATURE: 21.5,
    L1RoomSensor.DELAYED_ROOM_TEMPERATURE: 21.4,
    L1RoomSensor.ROOM_TEMPERATURE_SETPOINT: 21.0,
    L1RoomSensor.ROOM_SENSOR_POTENTIOMETER: 0.0,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ouman_eh_800.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="01JABCDEFGHIJKLMNOPQRSTUVW",
        domain=DOMAIN,
        title="Ouman EH-800",
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )


@pytest.fixture
def mock_ouman_client() -> Generator[AsyncMock]:
    """Mock the Ouman EH-800 client."""
    client = AsyncMock()
    client.get_active_registries.return_value = _REGISTRY_SET
    client.get_values.return_value = dict(_MOCK_VALUES)
    with (
        patch(
            "homeassistant.components.ouman_eh_800.coordinator.OumanEh800Client",
            return_value=client,
        ),
        patch(
            "homeassistant.components.ouman_eh_800.config_flow.OumanEh800Client",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ouman_client: AsyncMock,
    request: pytest.FixtureRequest,
) -> MockConfigEntry:
    """Set up the Ouman EH-800 integration for testing."""
    mock_config_entry.add_to_hass(hass)

    context = nullcontext()
    if platform := getattr(request, "param", None):
        context = patch("homeassistant.components.ouman_eh_800._PLATFORMS", [platform])

    with context:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
