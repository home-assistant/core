"""Test Alexa Devices button entities."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import setup_integration
from .const import TEST_USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_pressing_routine_button(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test routine run button."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.{slugify(TEST_USERNAME)}_test_routine"},
        blocking=True,
    )
    mock_amazon_devices_client.call_routine.assert_called_once()


@pytest.mark.parametrize(
    ("initial_routine", "updated_routines"),
    [
        (["Test Routine"], ["Test Routine", "New Routine"]),  # Add a routine
        (["Test Routine", "New Routine"], ["Test Routine"]),  # Remove a routine
        (["Test Routine"], []),  # Remove all routines
    ],
)
async def test_dynamic_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    initial_routine: list[str],
    updated_routines: list[str],
) -> None:
    """Test entities are dynamically created and deleted."""

    mock_amazon_devices_client.routines = initial_routine

    await setup_integration(hass, mock_config_entry)

    # Check initial routine(s) exist
    for routine in initial_routine:
        entity_id = f"button.{slugify(TEST_USERNAME)}_{slugify(routine)}"
        assert hass.states.get(entity_id) is not None

    mock_amazon_devices_client.routines = updated_routines

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # After update, check which routines should exist
    for routine in updated_routines:
        entity_id = f"button.{slugify(TEST_USERNAME)}_{slugify(routine)}"
        assert hass.states.get(entity_id) is not None

    # Check routines that were removed no longer exist
    for routine in set(initial_routine) - set(updated_routines):
        entity_id = f"button.{slugify(TEST_USERNAME)}_{slugify(routine)}"
        assert hass.states.get(entity_id) is None
