"""Test the SFR Box config flow."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from sfrbox_api.exceptions import SFRBoxError
from sfrbox_api.models import SystemInfo

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import load_fixture


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sfr_box.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_config_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        side_effect=SFRBoxError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    system_info = SystemInfo(**json.loads(load_fixture("system_getInfo.json", DOMAIN)))
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=system_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "SFR Box"
    assert result["data"][CONF_HOST] == "192.168.0.1"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("config_entry")
async def test_config_flow_duplicate_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
):
    """Test abort if unique_id configured."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    system_info = SystemInfo(**json.loads(load_fixture("system_getInfo.json", DOMAIN)))
    # Ensure mac doesn't match existing mock entry
    system_info.mac_addr = "aa:bb:cc:dd:ee:ff"
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=system_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.1",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("config_entry")
async def test_config_flow_duplicate_mac(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
):
    """Test abort if unique_id configured."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    system_info = SystemInfo(**json.loads(load_fixture("system_getInfo.json", DOMAIN)))
    with patch(
        "homeassistant.components.sfr_box.config_flow.SFRBox.system_get_info",
        return_value=system_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.0.2",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0
