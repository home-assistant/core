"""Test Habitica sensor platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("habitica", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry_with_subentry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Habitica sensor platform."""

    config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_subentry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_subentry.entry_id
    )


@pytest.mark.xfail(
    strict=True,
    reason="Equipped gear missing from the cached content raises KeyError",
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_attribute_sensor_skips_gear_missing_from_content(
    hass: HomeAssistant,
    config_entry_with_subentry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test gear released after the content was fetched is left out."""
    del habitica.get_content.return_value.data.gear.flat["body_special_aetherAmulet"]

    config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_subentry.state is ConfigEntryState.LOADED
    # The amulet adds 10 STR, so the snapshot values of 104 and 44 drop by 10
    state = hass.states.get("sensor.test_user_strength")
    assert state is not None
    assert state.state == "94"
    assert state.attributes["equipment"] == 34
