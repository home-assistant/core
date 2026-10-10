"""Test the OpenGarage config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.opengarage.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_opengarage")
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcdef"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"] == {
        "host": "http://1.1.1.1",
        "device_key": "AfsasdnfkjDD",
        "port": 80,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        ([None], "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: list[Any] | type[Exception],
    error_msg: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_opengarage.update_state.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    mock_opengarage.update_state.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcdef"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"] == {
        "host": "http://1.1.1.1",
        "device_key": "AfsasdnfkjDD",
        "port": 80,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_opengarage")
async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "http://1.1.1.1",
            "device_key": "AfsasdnfkjDD",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "http://1.1.1.1",
            "device_key": "AfsasdnfkjDD",
            "port": 80,
            "verify_ssl": False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
