"""Tests for the file config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.file import DOMAIN
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_CONFIG_NOTIFY = {
    "platform": "notify",
    "file_path": "some_file",
}
MOCK_OPTIONS_NOTIFY = {"timestamp": True}
MOCK_CONFIG_SENSOR = {
    "platform": "sensor",
    "file_path": "some/path",
}
MOCK_OPTIONS_SENSOR = {"value_template": "{{ value | round(1) }}"}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("platform", "data", "options"),
    [
        ("sensor", MOCK_CONFIG_SENSOR, MOCK_OPTIONS_SENSOR),
        ("notify", MOCK_CONFIG_NOTIFY, MOCK_OPTIONS_NOTIFY),
    ],
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
    options: dict[str, Any],
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

    user_input = {**data, **options}
    user_input.pop("platform")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == data
    assert result2["options"] == options
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("platform", "data", "options"),
    [
        ("sensor", MOCK_CONFIG_SENSOR, MOCK_OPTIONS_SENSOR),
        ("notify", MOCK_CONFIG_NOTIFY, MOCK_OPTIONS_NOTIFY),
    ],
)
async def test_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options)
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

    user_input = {**data, **options}
    user_input.pop("platform")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize("is_allowed", [False], ids=["not_allowed"])
@pytest.mark.parametrize(
    ("platform", "data", "options"),
    [
        ("sensor", MOCK_CONFIG_SENSOR, MOCK_OPTIONS_SENSOR),
        ("notify", MOCK_CONFIG_NOTIFY, MOCK_OPTIONS_NOTIFY),
    ],
)
async def test_not_allowed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
    options: dict[str, Any],
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

    user_input = {**data, **options}
    user_input.pop("platform")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"file_path": "not_allowed"}


@pytest.mark.parametrize(
    ("platform", "data", "options", "new_options"),
    [
        (
            "sensor",
            MOCK_CONFIG_SENSOR,
            MOCK_OPTIONS_SENSOR,
            {CONF_UNIT_OF_MEASUREMENT: "mm"},
        ),
        ("notify", MOCK_CONFIG_NOTIFY, MOCK_OPTIONS_NOTIFY, {"timestamp": False}),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_is_allowed_path: bool,
    platform: str,
    data: dict[str, Any],
    options: dict[str, Any],
    new_options: dict[str, Any],
) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options, version=2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=new_options,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == new_options

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.options == new_options
