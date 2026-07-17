"""Tests for the KEF config flow."""

import aiohttp
import pytest

from homeassistant.components.kef.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FakeKefConnector

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow_success(
    hass: HomeAssistant, mock_connector: FakeKefConnector
) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test KEF Speaker"
    assert result["data"] == {CONF_HOST: "192.168.1.100", "model": "XIO"}
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_connector: FakeKefConnector
) -> None:
    """Test a connection error in the user flow."""
    mock_connector.mac_address_error = aiohttp.ClientError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the speaker is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.101"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"
