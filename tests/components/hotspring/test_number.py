"""Tests for the Hot Spring number platform."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError
import pytest
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

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry

ENTITY_ID = "number.connectedspa_ddeeff_target_temperature"


async def test_number_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number entity state."""
    state = hass.states.get(ENTITY_ID)
    assert state == snapshot

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry == snapshot


async def test_set_target_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test setting target temperature."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 38,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(100)


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_set_target_temperature_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when setting target temperature."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    mock_hotspring.set_temperature.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 38,
            },
            blocking=True,
        )
