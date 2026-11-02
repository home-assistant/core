"""Tests for the Huum number entity."""

from unittest.mock import AsyncMock

from huum.const import SaunaStatus
from huum.exceptions import HuumError, RequestError, SafetyException
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
