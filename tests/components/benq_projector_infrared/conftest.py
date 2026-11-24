"""Common fixtures for the BenQ Projector Infrared tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from infrared_protocols.codes.benq.projector import BenQProjectorCode
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.benq_projector_infrared import PLATFORMS
from homeassistant.components.benq_projector_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    DEVICE_NAME,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title=DEVICE_NAME,
        data={CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_benq_to_command() -> Generator[MagicMock]:
    """Patch ``to_command`` on the BenQ code enum to return the code itself.

    This lets tests assert on the code enum value rather than on raw timings.
    """
    with patch.object(
        BenQProjectorCode, "to_command", autospec=True, side_effect=lambda self: self
    ) as mock:
        yield mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_benq_to_command: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the BenQ Projector Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.benq_projector_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
