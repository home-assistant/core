"""Test the Brottsplatskartan config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.brottsplatskartan.const import CONF_AREA, DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AREA: "none",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Brottsplatskartan HOME"
    assert result2["data"] == {
        "area": None,
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
        "app_id": "ha-1234567890",
    }


async def test_form_location(hass: HomeAssistant) -> None:
    """Test we get the form using location."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AREA: "none",
            CONF_LOCATION: {
                CONF_LATITUDE: 59.32,
                CONF_LONGITUDE: 18.06,
            },
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Brottsplatskartan 59.32, 18.06"
    assert result2["data"] == {
        "area": None,
        "latitude": 59.32,
        "longitude": 18.06,
        "app_id": "ha-1234567890",
    }


async def test_form_area(hass: HomeAssistant) -> None:
    """Test we get the form using area."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 59.32,
                CONF_LONGITUDE: 18.06,
            },
            CONF_AREA: "Stockholms län",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Brottsplatskartan Stockholms län"
    assert result2["data"] == {
        "latitude": None,
        "longitude": None,
        "area": "Stockholms län",
        "app_id": "ha-1234567890",
    }


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.brottsplatskartan.sensor.BrottsplatsKartan",
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Brottsplatskartan HOME"
    assert result2["data"] == {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
        "area": None,
        "app_id": "ha-1234567890",
    }


async def test_import_flow_location_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml with location."""

    with patch(
        "homeassistant.components.brottsplatskartan.sensor.BrottsplatsKartan",
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_LATITUDE: 59.32,
                CONF_LONGITUDE: 18.06,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Brottsplatskartan 59.32, 18.06"
    assert result2["data"] == {
        "latitude": 59.32,
        "longitude": 18.06,
        "area": None,
        "app_id": "ha-1234567890",
    }


async def test_import_flow_location_area_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml with location and area."""

    with patch(
        "homeassistant.components.brottsplatskartan.sensor.BrottsplatsKartan",
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_LATITUDE: 59.32,
                CONF_LONGITUDE: 18.06,
                CONF_AREA: ["Blekinge län"],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Brottsplatskartan Blekinge län"
    assert result2["data"] == {
        "latitude": None,
        "longitude": None,
        "area": "Blekinge län",
        "app_id": "ha-1234567890",
    }


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            "latitude": hass.config.latitude,
            "longitude": hass.config.longitude,
            "area": None,
            "app_id": "ha-1234567890",
        },
        unique_id="bpk-home",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.brottsplatskartan.sensor.BrottsplatsKartan",
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_configured"
