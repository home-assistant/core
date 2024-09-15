"""Tests for the ezbeq config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ezbeq
from homeassistant.components.ezbeq.const import (
    CONF_CODEC_EXTENDED_SENSOR,
    CONF_CODEC_SENSOR,
    CONF_EDITION_SENSOR,
    CONF_JELLYFIN_CODEC_SENSOR,
    CONF_JELLYFIN_DISPLAY_TITLE_SENSOR,
    CONF_JELLYFIN_LAYOUT_SENSOR,
    CONF_JELLYFIN_PROFILE_SENSOR,
    CONF_PREFERRED_AUTHOR,
    CONF_SOURCE_MEDIA_PLAYER,
    CONF_SOURCE_TYPE,
    CONF_TITLE_SENSOR,
    CONF_TMDB_SENSOR,
    CONF_YEAR_SENSOR,
    DEFAULT_NAME,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import JF_MOCK_CONFIG, MOCK_CONFIG

pytestmark = pytest.mark.asyncio


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        ezbeq.const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    # patch the connection test
    with patch(
        "homeassistant.components.ezbeq.config_flow.EzBEQConfigFlow.test_connection",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_CONFIG[CONF_HOST],
                CONF_PORT: MOCK_CONFIG[CONF_PORT],
                CONF_SOURCE_TYPE: MOCK_CONFIG[CONF_SOURCE_TYPE],
                CONF_SOURCE_MEDIA_PLAYER: MOCK_CONFIG[CONF_SOURCE_MEDIA_PLAYER],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    # do the rest of the flow
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TMDB_SENSOR: "sensor.tmdb",
            CONF_YEAR_SENSOR: "sensor.year",
            CONF_CODEC_SENSOR: "sensor.codec",
            CONF_CODEC_EXTENDED_SENSOR: "sensor.codec_extended",
            CONF_EDITION_SENSOR: "sensor.edition",
            CONF_TITLE_SENSOR: "sensor.title",
            CONF_PREFERRED_AUTHOR: "",
        },
    )
    await hass.async_block_till_done()

    assert result3["title"] == DEFAULT_NAME
    assert result3["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_fail_connection(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        ezbeq.const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    # patch the connection test
    with patch(
        "homeassistant.components.ezbeq.config_flow.EzBEQConfigFlow.test_connection",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_CONFIG[CONF_HOST],
                CONF_PORT: MOCK_CONFIG[CONF_PORT],
                CONF_SOURCE_TYPE: MOCK_CONFIG[CONF_SOURCE_TYPE],
                CONF_SOURCE_MEDIA_PLAYER: MOCK_CONFIG[CONF_SOURCE_MEDIA_PLAYER],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_JF_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        ezbeq.const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    # patch the connection test
    with patch(
        "homeassistant.components.ezbeq.config_flow.EzBEQConfigFlow.test_connection",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: JF_MOCK_CONFIG[CONF_HOST],
                CONF_PORT: JF_MOCK_CONFIG[CONF_PORT],
                CONF_SOURCE_TYPE: JF_MOCK_CONFIG[CONF_SOURCE_TYPE],
                CONF_SOURCE_MEDIA_PLAYER: JF_MOCK_CONFIG[CONF_SOURCE_MEDIA_PLAYER],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    # do the rest of the flow
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_JELLYFIN_CODEC_SENSOR: "sensor.jellyfin_codec",
            CONF_JELLYFIN_DISPLAY_TITLE_SENSOR: "sensor.jellyfin_display_title",
            CONF_JELLYFIN_PROFILE_SENSOR: "sensor.jellyfin_profile",
            CONF_JELLYFIN_LAYOUT_SENSOR: "sensor.jellyfin_layout",
            CONF_EDITION_SENSOR: "sensor.edition",
            CONF_TITLE_SENSOR: "sensor.title",
            CONF_PREFERRED_AUTHOR: "",
            CONF_TMDB_SENSOR: "sensor.tmdb",
            CONF_YEAR_SENSOR: "sensor.year",
        },
    )
    await hass.async_block_till_done()

    assert result3["title"] == DEFAULT_NAME
    assert result3["data"] == JF_MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1
