"""Tests for the Huum number entity."""

from unittest.mock import AsyncMock, patch

from huum.const import SaunaStatus
from huum.exceptions import HuumError, RequestError, SafetyException
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "number.huum_sauna_humidity"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.mark.usefixtures("init_integration")
async def test_number_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_humidity(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
) -> None:
    """Test setting the humidity."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 5,
        },
        blocking=True,
    )

    mock_huum_client.turn_on.assert_awaited_once_with(temperature=80, humidity=5)


@pytest.mark.usefixtures("init_integration")
async def test_dont_set_humidity_when_sauna_not_heating(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
) -> None:
    """Test setting the humidity."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_NOT_HEATING
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 5,
        },
        blocking=True,
    )

    mock_huum_client.turn_on.assert_not_called()


async def setup_number_platform(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration with only the number platform."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.huum.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_set_humidity_above_controller_maximum(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test humidity above the maximum reported by the controller is rejected."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    mock_huum_client.status.return_value.maximum_target_humidity = 10
    await setup_number_platform(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_MAX] == 10

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 20,
            },
            blocking=True,
        )

    mock_huum_client.turn_on.assert_not_called()


async def test_set_humidity_at_controller_maximum(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test humidity equal to the maximum reported by the controller is set."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    mock_huum_client.status.return_value.maximum_target_humidity = 10
    await setup_number_platform(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 10,
        },
        blocking=True,
    )

    mock_huum_client.turn_on.assert_awaited_once_with(temperature=80, humidity=10)


async def test_humidity_maximum_without_controller_value(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the library limit is used when the controller reports no maximum."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    mock_huum_client.status.return_value.target_temperature = 95
    mock_huum_client.status.return_value.maximum_target_humidity = None
    mock_huum_client.get_max_humidity.return_value = 0
    await setup_number_platform(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_MAX] == 0
    mock_huum_client.get_max_humidity.assert_called_with(95)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 5,
            },
            blocking=True,
        )

    mock_huum_client.turn_on.assert_not_called()


async def test_humidity_maximum_without_target_temperature(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the default maximum is used without a reported maximum or target."""
    mock_huum_client.status.return_value.target_temperature = None
    mock_huum_client.status.return_value.maximum_target_humidity = None
    await setup_number_platform(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_MAX] == 40
    mock_huum_client.get_max_humidity.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "message"),
    [
        pytest.param(
            SafetyException("Door is open"),
            "Unable to turn on the sauna",
            id="safety_exception",
        ),
        pytest.param(
            RequestError(),
            "An error occurred while communicating with the Huum sauna",
            id="communication_error",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_humidity_error(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    side_effect: HuumError,
    message: str,
) -> None:
    """Test that errors when setting the humidity are raised as HomeAssistantError."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    mock_huum_client.turn_on.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 5,
            },
            blocking=True,
        )
