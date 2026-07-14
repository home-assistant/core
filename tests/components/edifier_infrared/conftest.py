"""Common fixtures for the Edifier Infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.edifier.models import EdifierCommandSet, EdifierModel
import pytest

from homeassistant.components.edifier_infrared import PLATFORMS
from homeassistant.components.edifier_infrared.const import (
    CONF_COMMAND_SET,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="Edifier R1700BT via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_MODEL: EdifierModel.R1700BT.value,
            CONF_COMMAND_SET: EdifierCommandSet.R1700BT.value,
        },
        unique_id=f"r1700bt_{MOCK_INFRARED_EMITTER_ENTITY_ID}",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_edifier_code_to_command() -> Generator[None]:
    """Patch Edifier *Code.to_command to return the code enum directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw NEC timings.
    """
    with (
        patch(
            "infrared_protocols.codes.edifier.r1700bt.EdifierR1700BTCode.to_command",
            autospec=True,
            side_effect=lambda self: self,
        ),
        patch(
            "infrared_protocols.codes.edifier.r1280db.EdifierR1280DBCode.to_command",
            autospec=True,
            side_effect=lambda self: self,
        ),
        patch(
            "infrared_protocols.codes.edifier.r1280t.EdifierR1280TCode.to_command",
            autospec=True,
            side_effect=lambda self: self,
        ),
        patch(
            "infrared_protocols.codes.edifier.s360db.EdifierS360DBCode.to_command",
            autospec=True,
            side_effect=lambda self: self,
        ),
        patch(
            "infrared_protocols.codes.edifier.rc20g.EdifierRC20GCode.to_command",
            autospec=True,
            side_effect=lambda self: self,
        ),
        patch(
            "infrared_protocols.codes.edifier.s3000pro.EdifierS3000ProCode.to_command",
            autospec=True,
            side_effect=lambda self: self,
        ),
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_edifier_code_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Edifier Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.edifier_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
