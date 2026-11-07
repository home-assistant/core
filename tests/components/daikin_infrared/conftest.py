"""Common fixtures for the Daikin Infrared tests."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID as MOCK_INFRARED_RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

from homeassistant.components.daikin_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

ENTRY_ID = "01JTEST0000000000000000001"


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return True


@pytest.fixture
def mock_config_entry(has_receiver: bool) -> MockConfigEntry:
    """Return a mock config entry for the Daikin AC."""
    data: dict[str, Any] = {
        CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID
    }
    if has_receiver:
        data[CONF_INFRARED_RECEIVER_ENTITY_ID] = MOCK_INFRARED_RECEIVER_ENTITY_ID

    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="Daikin AC via Test IR emitter",
        data=data,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> MockConfigEntry:
    """Set up the Daikin Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
