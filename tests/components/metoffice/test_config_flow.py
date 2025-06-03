"""Test the MetOffice config flow."""

import datetime
import json
from unittest.mock import patch

import pytest
import requests_mock

from homeassistant import config_entries
from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from .const import (
    METOFFICE_CONFIG_WAVERTREE,
    TEST_API_KEY,
    TEST_LATITUDE_WAVERTREE,
    TEST_LONGITUDE_WAVERTREE,
    TEST_SITE_NAME_WAVERTREE,
)

from tests.common import MockConfigEntry, async_load_fixture


async def test_form(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test we get the form."""
    hass.config.latitude = TEST_LATITUDE_WAVERTREE
    hass.config.longitude = TEST_LONGITUDE_WAVERTREE

    # all metoffice test data encapsulated in here
    mock_json = json.loads(await async_load_fixture(hass, "metoffice.json", DOMAIN))
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.metoffice.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": TEST_API_KEY}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_SITE_NAME_WAVERTREE
    assert result2["data"] == {
        "api_key": TEST_API_KEY,
        "latitude": TEST_LATITUDE_WAVERTREE,
        "longitude": TEST_LONGITUDE_WAVERTREE,
        "name": TEST_SITE_NAME_WAVERTREE,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test we handle duplicate entries."""
    hass.config.latitude = TEST_LATITUDE_WAVERTREE
    hass.config.longitude = TEST_LONGITUDE_WAVERTREE

    # all metoffice test data encapsulated in here
    mock_json = json.loads(await async_load_fixture(hass, "metoffice.json", DOMAIN))
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_LATITUDE_WAVERTREE}_{TEST_LONGITUDE_WAVERTREE}",
        data=METOFFICE_CONFIG_WAVERTREE,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=METOFFICE_CONFIG_WAVERTREE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_cannot_connect(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test we handle cannot connect error."""
    hass.config.latitude = TEST_LATITUDE_WAVERTREE
    hass.config.longitude = TEST_LONGITUDE_WAVERTREE

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily", text=""
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": TEST_API_KEY},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant, mock_simple_manager_fail
) -> None:
    """Test we handle unknown error."""
    mock_instance = mock_simple_manager_fail.return_value
    mock_instance.get_forecast.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": TEST_API_KEY},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_reauth_flow(
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

    await entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
