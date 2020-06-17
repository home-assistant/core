"""Test the National Weather Service (NWS) config flow."""
import json

from homeassistant import config_entries, setup
from homeassistant.components.metoffice.const import DOMAIN

from .const import (
    METOFFICE_CONFIG_WAVERTREE,
    TEST_API_KEY,
    TEST_LATITUDE_WAVERTREE,
    TEST_LONGITUDE_WAVERTREE,
    TEST_SITE_NAME_WAVERTREE,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture


async def test_form(hass, requests_mock):
    """Test we get the form."""
    hass.config.latitude = TEST_LATITUDE_WAVERTREE
    hass.config.longitude = TEST_LONGITUDE_WAVERTREE

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.metoffice.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.metoffice.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": TEST_API_KEY}
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_SITE_NAME_WAVERTREE
    assert result2["data"] == {
        "api_key": TEST_API_KEY,
        "latitude": TEST_LATITUDE_WAVERTREE,
        "longitude": TEST_LONGITUDE_WAVERTREE,
        "name": TEST_SITE_NAME_WAVERTREE,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(hass, requests_mock):
    """Test we handle duplicate entries."""
    hass.config.latitude = TEST_LATITUDE_WAVERTREE
    hass.config.longitude = TEST_LONGITUDE_WAVERTREE

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))

    all_sites = json.dumps(mock_json["all_sites"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text="",
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

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_form_cannot_connect(hass, requests_mock):
    """Test we handle cannot connect error."""
    hass.config.latitude = TEST_LATITUDE_WAVERTREE
    hass.config.longitude = TEST_LONGITUDE_WAVERTREE

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": TEST_API_KEY},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass, mock_simple_manager_fail):
    """Test we handle unknown error."""
    mock_instance = mock_simple_manager_fail.return_value
    mock_instance.get_nearest_forecast_site.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": TEST_API_KEY},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
