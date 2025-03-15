"""Tests for Google Maps Travel Time init."""

import pytest

from homeassistant.components.google_travel_time.const import (
    ARRIVAL_TIME,
    CONF_TIME,
    CONF_TIME_TYPE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DEFAULT_OPTIONS, MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("v1", "v2", "caplog_message"),
    [
        ("08:00", "08:00", None),
        ("08:00:00", "08:00:00", None),
        ("1742144400", "17:00", None),
        ("now", None, None),
        (None, None, None),
        ("invalid", None, "Invalid time format found while migrating"),
    ],
)
@pytest.mark.usefixtures("validate_config_entry")
async def test_migrate_entry_v1_v2(
    hass: HomeAssistant,
    v1: str,
    v2: str | None,
    caplog_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test successful migration of entry data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            **DEFAULT_OPTIONS,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: v1,
        },
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.options[CONF_TIME] == v2
    if caplog_message:
        assert caplog_message in caplog.text
