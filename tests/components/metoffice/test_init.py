"""Tests for metoffice init."""

import datetime as dt
import json

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)
import requests_mock

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import utcnow

from .const import (
    METOFFICE_CONFIG_WAVERTREE,
    TEST_API_KEY,
    TEST_LATITUDE_WAVERTREE,
    TEST_LONGITUDE_WAVERTREE,
    TEST_SITE_NAME_WAVERTREE,
)


@pytest.mark.freeze_time(dt.datetime(2024, 11, 23, 12, tzinfo=dt.UTC))
async def test_reauth_on_auth_error(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
) -> None:
    """Test handling authentication errors and reauth flow."""
    mock_json = await async_load_json_object_fixture(hass, "metoffice.json", DOMAIN)
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 1

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text="",
        status_code=401,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text="",
        status_code=401,
    )

    future_time = utcnow() + dt.timedelta(minutes=40)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_migrate_entry(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test entry migration."""
    # all metoffice test data encapsulated in here
    mock_json = await async_load_json_object_fixture(hass, "metoffice.json", DOMAIN)
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: TEST_API_KEY,
            CONF_LATITUDE: TEST_LATITUDE_WAVERTREE,
            CONF_LONGITUDE: TEST_LONGITUDE_WAVERTREE,
            CONF_NAME: TEST_SITE_NAME_WAVERTREE,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data == METOFFICE_CONFIG_WAVERTREE
    assert entry.version == 2
