"""Tests for the ZAMG component."""

from homeassistant import config_entries
from homeassistant.components.zamg.const import CONF_STATION_ID, DOMAIN as ZAMG_DOMAIN

from .conftest import TEST_STATION_ID, TEST_STATION_NAME

FIXTURE_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": ZAMG_DOMAIN,
    "title": TEST_STATION_NAME,
    "data": {
        CONF_STATION_ID: TEST_STATION_ID,
    },
    "options": None,
    "source": config_entries.SOURCE_USER,
    "unique_id": TEST_STATION_ID,
}
