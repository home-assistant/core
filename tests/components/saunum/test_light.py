"""Test the Saunum light platform."""

from __future__ import annotations

from dataclasses import replace

from pysaunum import SaunumException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_state", "client_method", "expected_args"),
    [
        (SERVICE_TURN_ON, STATE_ON, "async_set_light_control", (True,)),
        (SERVICE_TURN_OFF, STATE_OFF, "async_set_light_control", (False,)),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_light_service_calls(
    hass: HomeAssistant,
    mock_saunum_client,
    service: str,
    expected_state: str,
    client_method: str,
    expected_args: tuple,
) -> None:
    """Test light service calls."""
    entity_id = "light.saunum_leil_light"

    # Mock the client method to update the coordinator data
    async def update_light_state(*args):
        """Update the light state in mock data."""
        current_data = mock_saunum_client.async_get_data.return_value
        mock_saunum_client.async_get_data.return_value = replace(
            current_data, light_on=(expected_state == STATE_ON)
        )

    getattr(mock_saunum_client, client_method).side_effect = update_light_state

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_saunum_client, client_method).assert_called_once_with(*expected_args)

    # Verify state updated
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_error"),
    [
        (SERVICE_TURN_ON, "Failed to turn on light"),
        (SERVICE_TURN_OFF, "Failed to turn off light"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_light_service_call_failure(
    hass: HomeAssistant,
    mock_saunum_client,
    service: str,
    expected_error: str,
) -> None:
    """Test handling of light service call failures."""
    entity_id = "light.saunum_leil_light"

    # Make the client method raise an exception
    mock_saunum_client.async_set_light_control.side_effect = SaunumException(
        "Connection lost"
    )

    with pytest.raises(HomeAssistantError, match=expected_error):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
