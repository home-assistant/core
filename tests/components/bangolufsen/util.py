"""Tools for testing bangolufsen."""

from homeassistant.components.bangolufsen.const import DOMAIN

from .const import TestConstantsConfigFlow as tc

from tests.common import MockConfigEntry


def mock_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=tc.TEST_SERIAL_NUMBER,
        data=tc.TEST_DATA_FULL,
        title=tc.TEST_NAME,
    )
