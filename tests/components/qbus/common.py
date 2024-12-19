"""Define common test values."""

from homeassistant.components.qbus.const import DOMAIN

from tests.common import MockConfigEntry


def qbus_config_entry() -> MockConfigEntry:
    """Config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="ctd_000001",
        entry_id="ctd_000001",
        data={},
    )
