"""Test for sensor platform of the Bring! integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bring.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.bring.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("mock_bring_client")
async def test_setup(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of sensor platform."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, bring_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("fixture", "entity_state"),
    [
        ("items_invitation", "invitation"),
        ("items_shared", "shared"),
        ("items", "registered"),
    ],
)
async def test_list_access_states(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    fixture: str,
    entity_state: str,
) -> None:
    """Snapshot test states of list access sensor."""

    mock_bring_client.get_list.return_value = load_json_object_fixture(
        f"{fixture}.json", DOMAIN
    )

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("sensor.einkauf_list_access"))
    assert state.state == entity_state
