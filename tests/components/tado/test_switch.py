"""The switch tests for the tado platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tado import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .util import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform

CHILD_LOCK_SWITCH_ENTITY = "switch.baseboard_heater_child_lock"


@pytest.fixture(autouse=True)
def setup_platforms() -> AsyncGenerator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test creation of switch entities."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("method", "expected"), [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)]
)
async def test_set_child_lock(hass: HomeAssistant, method, expected) -> None:
    """Test enable child lock on switch."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.set_child_lock"
    ) as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            method,
            {ATTR_ENTITY_ID: CHILD_LOCK_SWITCH_ENTITY},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    assert mock_set_state.call_args[0][1] is expected
