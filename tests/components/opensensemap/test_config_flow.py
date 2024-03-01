"""Test openSenseMap config flow."""
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.opensensemap.const import CONF_STATION_ID, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_STATION_ID, VALID_STATION_NAME

from tests.common import MockConfigEntry

TEST_STATION_ID_INVALID = "Invalid-StationId"


async def test_user_flow(
    hass: HomeAssistant, setup_entry_mock: AsyncMock, osm_api_mock: AsyncMock
) -> None:
    """Test configuration flow initialized by the user."""

    with setup_entry_mock, osm_api_mock:
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result1["type"] == FlowResultType.FORM
        assert not result1["errors"]

        # check with invalid data
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={
                CONF_STATION_ID: TEST_STATION_ID_INVALID,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_STATION_ID] == "invalid_id"

        # check with valid data
        result3 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={
                CONF_STATION_ID: VALID_STATION_ID,
            },
        )
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == VALID_STATION_NAME
        assert result3["data"] == {
            CONF_STATION_ID: VALID_STATION_ID,
            CONF_NAME: VALID_STATION_NAME,
        }


async def test_user_flow_cant_connect_failure(
    hass: HomeAssistant,
    setup_entry_mock: AsyncMock,
    osm_api_failed_mock: AsyncMock,
) -> None:
    """Test configuration flow with server not accesable error."""

    with setup_entry_mock, osm_api_failed_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_STATION_ID: VALID_STATION_ID,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STATION_ID: VALID_STATION_ID}
        )


async def test_already_exists_flow(
    hass: HomeAssistant,
    setup_entry_mock: AsyncMock,
    osm_api_mock: AsyncMock,
    valid_config_entry: MockConfigEntry,
) -> None:
    """Test the flow when same id already exists."""
    valid_config_entry.add_to_hass(hass)
    with setup_entry_mock, osm_api_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_STATION_ID: VALID_STATION_ID,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("config", "title", "data"),
    [
        (
            {
                CONF_STATION_ID: VALID_STATION_ID,
            },
            VALID_STATION_NAME,
            {
                CONF_STATION_ID: VALID_STATION_ID,
                CONF_NAME: VALID_STATION_NAME,
            },
        ),
        (
            {
                CONF_STATION_ID: VALID_STATION_ID,
                CONF_NAME: "custom_name",
            },
            "custom_name",
            {
                CONF_STATION_ID: VALID_STATION_ID,
                CONF_NAME: "custom_name",
            },
        ),
    ],
)
async def test_import_flow(
    hass: HomeAssistant,
    config: dict[str, Any],
    title: str,
    data: dict[str, Any],
    setup_entry_mock: AsyncMock,
    osm_api_mock: AsyncMock,
) -> None:
    """Test the import flow."""
    with setup_entry_mock, osm_api_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data


async def test_import_flow_failures(
    hass: HomeAssistant, setup_entry_mock: AsyncMock, osm_api_mock: AsyncMock
) -> None:
    """Test the import flow."""
    with setup_entry_mock, osm_api_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_id"


async def test_importing_already_exists_flow(
    hass: HomeAssistant,
    valid_config_entry: MockConfigEntry,
    setup_entry_mock: AsyncMock,
    osm_api_mock: AsyncMock,
) -> None:
    """Test the import flow when same location already exists."""
    valid_config_entry.add_to_hass(hass)
    with setup_entry_mock, osm_api_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_STATION_ID: VALID_STATION_ID,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_import_flow_cant_connect(
    hass: HomeAssistant,
    setup_entry_mock: AsyncMock,
    osm_api_failed_mock: AsyncMock,
) -> None:
    """Test the import flow."""
    with setup_entry_mock, osm_api_failed_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"
