"""Tests for metoffice init."""

import datetime
import json

import pytest
import requests_mock

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import utcnow

from .const import METOFFICE_CONFIG_WAVERTREE

from tests.common import MockConfigEntry, async_fire_time_changed, async_load_fixture


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_reauth_on_auth_error(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test handling authentication errors and reauth flow."""
    mock_json = json.loads(await async_load_fixture(hass, "metoffice.json", DOMAIN))
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

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
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

    future_time = utcnow() + datetime.timedelta(minutes=40)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
