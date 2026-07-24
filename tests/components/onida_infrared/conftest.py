"""Common fixtures for the Onida Infrared tests."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.onida_infrared import PLATFORMS
from homeassistant.components.onida_infrared.const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID as MOCK_INFRARED_RECEIVER_ENTITY_ID,
)
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

ENTRY_ID = "01JTEST0000000000000000001"


@pytest.fixture
def hvac_modes() -> list[HVACMode]:
    """Return the HVAC modes configured on the config entry."""
    return [HVACMode.COOL, HVACMode.DRY]


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return True


@pytest.fixture
def extra_entry_data(hvac_modes: list[HVACMode]) -> dict[str, Any]:
    """Return the config entry data beyond the emitter/receiver ids."""
    return {CONF_HVAC_MODES: hvac_modes}


@pytest.fixture
def mock_config_entry(
    extra_entry_data: dict[str, Any],
    has_receiver: bool,
) -> MockConfigEntry:
    """Return a mock config entry for the Onida AC."""
    data: dict[str, Any] = {
        CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        **extra_entry_data,
    }
    if has_receiver:
        data[CONF_INFRARED_RECEIVER_ENTITY_ID] = MOCK_INFRARED_RECEIVER_ENTITY_ID

    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="Onida AC via Test IR emitter",
        data=data,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Onida Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.onida_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
