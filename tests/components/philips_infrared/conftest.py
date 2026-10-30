"""Common fixtures for the Philips Infrared tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from infrared_protocols.codes.philips.tv import PhilipsTVCode
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.philips_infrared import PLATFORMS
from homeassistant.components.philips_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

ENTRY_ID = "01JTEST0000000000000000000"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="Philips TV via Test IR emitter",
        data={CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_philips_to_command() -> Generator[MagicMock]:
    """Patch ``PhilipsTVCode.to_command`` to return the code itself.

    This lets tests assert on the high-level code enum value rather than
    on the raw RC-6 timings. The mock is yielded so tests can also
    inspect call arguments, such as the RC-6 toggle bit.
    """
    with patch.object(
        PhilipsTVCode,
        "to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ) as mock:
        yield mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_philips_to_command: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Philips Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.philips_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
