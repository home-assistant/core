"""The switch tests for the tado platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

CHILD_LOCK_SWITCH_ENTITY = "switch.baseboard_heater_child_lock"


@pytest.fixture(autouse=True)
def setup_platforms() -> AsyncGenerator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SWITCH]):
        yield


async def trigger_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an update of the Tado integration.

    Since the binary sensor platform doesn't infer a state immediately without extra requests,
    so adding this here to remove in a follow-up PR.
    """
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_tado_api")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of switch entities."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("method", "expected"), [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)]
)
async def test_set_child_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    expected: bool,
) -> None:
    """Test enable child lock on switch."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        method,
        {ATTR_ENTITY_ID: CHILD_LOCK_SWITCH_ENTITY},
        blocking=True,
    )

    mock_tado_api.set_child_lock.assert_called_once()
    assert mock_tado_api.set_child_lock.call_args[1]["child_lock"] is expected
