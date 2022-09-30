"""Test the Matter config flow."""
from unittest.mock import patch

from matter_server.client.exceptions import CannotConnect, InvalidServerVersion
import pytest

from homeassistant import config_entries
from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_create_entry(hass: HomeAssistant) -> None:
    """Test user step create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("homeassistant.components.matter.config_flow.Client.connect",), patch(
        "homeassistant.components.matter.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://172.30.32.1:5580/chip_ws",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "http://172.30.32.1:5580/chip_ws"
    assert result["data"] == {
        "url": "http://172.30.32.1:5580/chip_ws",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error, side_effect",
    [
        ("cannot_connect", CannotConnect(Exception("Boom"))),
        ("invalid_server_version", InvalidServerVersion("Invalid version")),
        ("unknown", Exception("Unknown boom")),
    ],
)
async def test_user_errors(
    hass: HomeAssistant, error: str, side_effect: Exception
) -> None:
    """Test user step cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matter.config_flow.Client.connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://172.30.32.1:5580/chip_ws",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_user_abort_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test user step abort as single instance only allowed."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "http://172.30.32.1:5580/chip_ws"}, title="Matter"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
