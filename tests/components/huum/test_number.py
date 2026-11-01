"""Tests for the Huum number entity."""

from unittest.mock import AsyncMock, patch

from huum.const import SaunaStatus
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
from homeassistant.exceptions import ServiceValidationError
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


async def test_set_humidity_above_controller_maximum(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test humidity above the maximum reported by the controller is rejected."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    mock_huum_client.status.return_value.maximum_target_humidity = 10

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.huum.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

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
