"""The switch tests for the tado platform."""

from collections.abc import Generator
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
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

CHILD_LOCK_SWITCH_ENTITY = "switch.wr4_child_lock"


@pytest.fixture(autouse=True)
def setup_platforms() -> Generator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of switch entities."""

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    entity_entry = entity_registry.async_get(CHILD_LOCK_SWITCH_ENTITY)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert (DOMAIN, "WR4") in device_entry.identifiers


@pytest.mark.parametrize(
    ("method", "expected"), [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)]
)
@pytest.mark.usefixtures("init_integration")
async def test_set_child_lock(hass: HomeAssistant, method, expected) -> None:
    """Test enable child lock on switch."""

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.set_child_lock"
    ) as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            method,
            {ATTR_ENTITY_ID: CHILD_LOCK_SWITCH_ENTITY},
            blocking=True,
        )

    mock_set_state.assert_called_once_with("WR4", expected)
