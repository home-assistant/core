"""Tests for the file config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.file import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_CONFIG_NOTIFY = {
    "platform": "notify",
    "file_path": "some_file",
    "timestamp": True,
}
MOCK_CONFIG_SENSOR = {
    "platform": "sensor",
    "file_path": "some/path",
    "value_template": "{{ value | round(1) }}",
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("platform", "data"),
    [("sensor", MOCK_CONFIG_SENSOR), ("notify", MOCK_CONFIG_NOTIFY)],
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": platform},
    )
    await hass.async_block_till_done()

    user_input = dict(data)
    user_input.pop("platform")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == data
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("platform", "data"),
    [("sensor", MOCK_CONFIG_SENSOR), ("notify", MOCK_CONFIG_NOTIFY)],
)
async def test_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": platform},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == platform

    user_input = dict(data)
    user_input.pop("platform")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize("is_allowed", [False], ids=["not_allowed"])
@pytest.mark.parametrize(
    ("platform", "data"),
    [("sensor", MOCK_CONFIG_SENSOR), ("notify", MOCK_CONFIG_NOTIFY)],
)
async def test_not_allowed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
) -> None:
    """Test aborting if the file path is not allowed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": platform},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == platform

    user_input = dict(data)
    user_input.pop("platform")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"file_path": "not_allowed"}
