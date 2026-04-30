"""Common fixtures for the Novy Cooker Hood tests."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rf_protocols import CodeCollection

from homeassistant.components.novy_cooker_hood.const import (
    CONF_CODE,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import (
    MockRadioFrequencyCommand,
    MockRadioFrequencyEntity,
)

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"


@pytest.fixture(autouse=True)
def mock_get_codes() -> Iterator[MagicMock]:
    """Patch the bundled-codes loader so tests don't hit the filesystem."""
    fake_collection = MagicMock(spec=CodeCollection)
    fake_collection.async_load_command = AsyncMock(
        side_effect=lambda name: MockRadioFrequencyCommand()
    )
    with patch(
        "homeassistant.components.novy_cooker_hood.commands.get_codes",
        return_value=fake_collection,
    ):
        yield fake_collection


@pytest.fixture
def mock_config_entry(
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> MockConfigEntry:
    """Return a mock config entry for Novy Cooker Hood."""
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert entity_entry is not None
    return MockConfigEntry(
        domain=DOMAIN,
        title="Novy Cooker Hood",
        data={CONF_TRANSMITTER: entity_entry.id, CONF_CODE: 1},
        unique_id=f"{entity_entry.id}_1",
    )


@pytest.fixture
async def init_novy_cooker_hood(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Novy Cooker Hood integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
