"""Common fixtures for the LG Infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.lg_infrared import PLATFORMS
from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import ENTITY_ID as MOCK_INFRARED_ENTITY_ID
from tests.components.infrared.common import MockInfraredEntity


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="LG TV via Test IR transmitter",
        data={
            CONF_DEVICE_TYPE: LGDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=f"lg_ir_tv_{MOCK_INFRARED_ENTITY_ID}",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_lg_tv_code_to_command() -> Generator[None]:
    """Patch LGTVCode.to_command to return the LGTVCode directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw NEC timings.
    """
    with patch(
        "homeassistant.components.lg_infrared.entity.LGTVCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
    mock_lg_tv_code_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the LG Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lg_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
