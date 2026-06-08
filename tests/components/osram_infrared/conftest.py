"""Common fixtures for the OSRAM infrared tests."""

import pytest

from homeassistant.components.osram_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    get_unique_id,
)

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID as MOCK_INFRARED_RECEIVER_ENTITY_ID,
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock OSRAM infrared config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="OSRAM light via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
        },
        unique_id=get_unique_id(MOCK_INFRARED_EMITTER_ENTITY_ID),
    )
