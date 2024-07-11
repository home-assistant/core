"""Tests for the Spider config flow."""

from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.spider.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USERNAME = "spider-username"
PASSWORD = "spider-password"

SPIDER_USER_DATA = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
}


@pytest.fixture(name="spider")
def spider_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.spider.config_flow.SpiderApi") as spider:
        yield spider


async def test_user(hass: HomeAssistant, spider) -> None:
    """Test user config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.spider.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.spider.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=SPIDER_USER_DATA
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert not result["result"].unique_id

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass: HomeAssistant, spider) -> None:
    """Test import step."""

    with (
        patch(
            "homeassistant.components.spider.async_setup",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.spider.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=SPIDER_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert not result["result"].unique_id

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(hass: HomeAssistant, spider) -> None:
    """Test we abort if Spider is already setup."""
    MockConfigEntry(domain=DOMAIN, data=SPIDER_USER_DATA).add_to_hass(hass)

    # Should fail, config exist (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=SPIDER_USER_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

    # Should fail, config exist (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=SPIDER_USER_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
