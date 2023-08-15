"""Test OpenSky config flow."""
from typing import Any

import pytest

from homeassistant.components.opensky.const import CONF_ALTITUDE, DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_RADIUS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import patch_setup_entry

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    with patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_RADIUS: 10,
                CONF_LATITUDE: 0.0,
                CONF_LONGITUDE: 0.0,
                CONF_ALTITUDE: 0,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "OpenSky"
        assert result["data"] == {
            CONF_LATITUDE: 0.0,
            CONF_LONGITUDE: 0.0,
        }
        assert result["options"] == {
            CONF_ALTITUDE: 0.0,
            CONF_RADIUS: 10.0,
        }


@pytest.mark.parametrize(
    ("config", "title", "data", "options"),
    [
        (
            {CONF_RADIUS: 10.0},
            DEFAULT_NAME,
            {
                CONF_LATITUDE: 32.87336,
                CONF_LONGITUDE: -117.22743,
            },
            {
                CONF_RADIUS: 10000.0,
                CONF_ALTITUDE: 0,
            },
        ),
        (
            {
                CONF_RADIUS: 10.0,
                CONF_NAME: "My home",
            },
            "My home",
            {
                CONF_LATITUDE: 32.87336,
                CONF_LONGITUDE: -117.22743,
            },
            {
                CONF_RADIUS: 10000.0,
                CONF_ALTITUDE: 0,
            },
        ),
        (
            {
                CONF_RADIUS: 10.0,
                CONF_LATITUDE: 10.0,
                CONF_LONGITUDE: -100.0,
            },
            DEFAULT_NAME,
            {
                CONF_LATITUDE: 10.0,
                CONF_LONGITUDE: -100.0,
            },
            {
                CONF_RADIUS: 10000.0,
                CONF_ALTITUDE: 0,
            },
        ),
        (
            {CONF_RADIUS: 10.0, CONF_ALTITUDE: 100.0},
            DEFAULT_NAME,
            {
                CONF_LATITUDE: 32.87336,
                CONF_LONGITUDE: -117.22743,
            },
            {
                CONF_RADIUS: 10000.0,
                CONF_ALTITUDE: 100.0,
            },
        ),
    ],
)
async def test_import_flow(
    hass: HomeAssistant,
    config: dict[str, Any],
    title: str,
    data: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test the import flow."""
    with patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["options"] == options
        assert result["data"] == data


async def test_importing_already_exists_flow(hass: HomeAssistant) -> None:
    """Test the import flow when same location already exists."""
    MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={},
        options={
            CONF_LATITUDE: 32.87336,
            CONF_LONGITUDE: -117.22743,
            CONF_RADIUS: 10.0,
            CONF_ALTITUDE: 100.0,
        },
    ).add_to_hass(hass)
    with patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: 32.87336,
                CONF_LONGITUDE: -117.22743,
                CONF_RADIUS: 10.0,
                CONF_ALTITUDE: 100.0,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
