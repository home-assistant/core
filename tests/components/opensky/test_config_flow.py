"""Test OpenSky config flow."""
from typing import Any
from unittest.mock import patch

import pytest
from python_opensky.exceptions import OpenSkyUnauthenticatedError

from homeassistant import data_entry_flow
from homeassistant.components.opensky.const import (
    CONF_ALTITUDE,
    CONF_CONTRIBUTING_USER,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RADIUS,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import get_states_response_fixture, patch_setup_entry
from .conftest import ComponentSetup

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


@pytest.mark.parametrize(
    ("user_input", "error"),
    [
        (
            {CONF_USERNAME: "homeassistant", CONF_CONTRIBUTING_USER: False},
            "password_missing",
        ),
        ({CONF_PASSWORD: "secret", CONF_CONTRIBUTING_USER: False}, "username_missing"),
        ({CONF_CONTRIBUTING_USER: True}, "no_authentication"),
        (
            {
                CONF_USERNAME: "homeassistant",
                CONF_PASSWORD: "secret",
                CONF_CONTRIBUTING_USER: True,
            },
            "invalid_auth",
        ),
    ],
)
async def test_options_flow_failures(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    user_input: dict[str, Any],
    error: str,
) -> None:
    """Test load and unload entry."""
    await setup_integration(config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch(
        "python_opensky.OpenSky.authenticate",
        side_effect=OpenSkyUnauthenticatedError(),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_RADIUS: 10000, **user_input},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == error
    with patch("python_opensky.OpenSky.authenticate"), patch(
        "python_opensky.OpenSky.get_states",
        return_value=get_states_response_fixture("opensky/states_1.json"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RADIUS: 10000,
                CONF_USERNAME: "homeassistant",
                CONF_PASSWORD: "secret",
                CONF_CONTRIBUTING_USER: True,
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_RADIUS: 10000,
            CONF_USERNAME: "homeassistant",
            CONF_PASSWORD: "secret",
            CONF_CONTRIBUTING_USER: True,
        }
