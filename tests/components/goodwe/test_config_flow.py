"""Test the Goodwe config flow."""

from unittest.mock import MagicMock, patch

from goodwe import InverterError
from goodwe.const import GOODWE_UDP_PORT

from homeassistant.components.goodwe.const import (
    CONF_MODEL_FAMILY,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_SERIAL

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_PORT = GOODWE_UDP_PORT


async def test_manual_setup(hass: HomeAssistant, mock_inverter: MagicMock) -> None:
    """Test manually setting up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.goodwe.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_MODEL_FAMILY: "MagicMock",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_setup_already_exists(
    hass: HomeAssistant, mock_inverter: MagicMock
) -> None:
    """Test manually setting up and the device already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
        unique_id=TEST_SERIAL,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with patch("homeassistant.components.goodwe.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_setup_device_offline(hass: HomeAssistant) -> None:
    """Test manually setting up, device offline."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with patch(
        "homeassistant.components.goodwe.config_flow.connect",
        side_effect=InverterError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_error"}
