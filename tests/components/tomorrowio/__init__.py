"""Tests for the Tomorrow.io Weather API integration."""

from typing import Any

from homeassistant.components.tomorrowio.const import (
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
    SUBENTRY_TYPE_LOCATION,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME

from .const import API_KEY, API_V4_ENTRY_DATA, TEST_LOCATION, TEST_SUBENTRY_ID

from tests.common import MockConfigEntry


def make_location_subentry_data(
    location: dict[str, float] | None = None,
    name: str = DEFAULT_NAME,
    timestep: int = DEFAULT_TIMESTEP,
    subentry_id: str = TEST_SUBENTRY_ID,
) -> ConfigSubentryDataWithId:
    """Return subentry data for a location subentry."""
    if location is None:
        location = TEST_LOCATION
    return ConfigSubentryDataWithId(
        data={CONF_LOCATION: location, CONF_NAME: name, CONF_TIMESTEP: timestep},
        subentry_id=subentry_id,
        subentry_type=SUBENTRY_TYPE_LOCATION,
        title=name,
        unique_id=f"{location[CONF_LATITUDE]}_{location[CONF_LONGITUDE]}",
    )


def make_v2_config_entry(
    subentries_data: list[ConfigSubentryDataWithId] | None = None,
    data: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Return a version 2 Tomorrow.io config entry."""
    if subentries_data is None:
        subentries_data = [make_location_subentry_data()]
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data=data or API_V4_ENTRY_DATA,
        unique_id=API_KEY,
        version=2,
        subentries_data=subentries_data,
    )
