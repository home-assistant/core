"""Common fixtures for the Sony Infrared tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.sony_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SonyDeviceType,
)
from homeassistant.core import HomeAssistant

ENTRY_ID = "01JTEST0000000000000000000"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sony_infrared.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def device_type() -> SonyDeviceType:
    """Return the device type of the config entry."""
    return SonyDeviceType.TV


@pytest.fixture
def mock_config_entry(device_type: SonyDeviceType) -> MockConfigEntry:
    """Return a mock config entry for the configured device type."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title=f"Sony {device_type.upper()} via Test IR emitter",
        data={
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> MockConfigEntry:
    """Set up the Sony Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
