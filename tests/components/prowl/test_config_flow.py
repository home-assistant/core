"""Test Prowl config flow."""

from unittest.mock import AsyncMock

import prowlpy
import pytest

from homeassistant import config_entries
from homeassistant.components.prowl.const import (
    CONF_LEGACY_SERVICE_NAME,
    CONF_NAMES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    BAD_API_RESPONSE,
    CONF_INPUT,
    INVALID_API_KEY_ERROR,
    TEST_API_KEY,
    TIMEOUT_ERROR,
)

from tests.common import MockConfigEntry


async def test_flow_user(hass: HomeAssistant, mock_prowlpy: AsyncMock) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Prowl"
    assert result["data"] == {CONF_API_KEY: CONF_INPUT[CONF_API_KEY]}


async def test_flow_duplicate_api_key(
    hass: HomeAssistant, mock_prowlpy: AsyncMock
) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT


async def test_flow_user_bad_key(hass: HomeAssistant, mock_prowlpy: AsyncMock) -> None:
    """Test user submitting a bad API key."""
    mock_prowlpy.verify_key.side_effect = prowlpy.APIError("Invalid API key")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == INVALID_API_KEY_ERROR

    mock_prowlpy.verify_key.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_prowl_timeout(
    hass: HomeAssistant, mock_prowlpy: AsyncMock
) -> None:
    """Test Prowl API timeout."""
    mock_prowlpy.verify_key.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == TIMEOUT_ERROR

    mock_prowlpy.verify_key.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_api_failure(hass: HomeAssistant, mock_prowlpy: AsyncMock) -> None:
    """Test Prowl API failure."""
    mock_prowlpy.verify_key.side_effect = prowlpy.APIError(BAD_API_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == BAD_API_RESPONSE

    mock_prowlpy.verify_key.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("names", "expected_title", "expected_data"),
    [
        pytest.param(["My Prowl"], "My Prowl", CONF_INPUT, id="with_name"),
        pytest.param(
            [None],
            "Prowl",
            {**CONF_INPUT, CONF_LEGACY_SERVICE_NAME: "notify"},
            id="without_name",
        ),
        pytest.param(
            ["one", "two"],
            "one, two",
            {**CONF_INPUT, CONF_LEGACY_SERVICE_NAME: "one"},
            id="several_names",
        ),
        pytest.param(
            [None, "two"],
            "notify, two",
            {**CONF_INPUT, CONF_LEGACY_SERVICE_NAME: "notify"},
            id="several_names_first_without_name",
        ),
    ],
)
@pytest.mark.usefixtures("mock_prowlpy")
async def test_flow_import(
    hass: HomeAssistant,
    names: list[str | None],
    expected_title: str,
    expected_data: dict[str, str],
) -> None:
    """Test importing the YAML configuration of an API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_API_KEY: TEST_API_KEY, CONF_NAMES: names},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == expected_data


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(config_entries.SOURCE_USER, id="set_up_in_ui"),
        pytest.param(config_entries.SOURCE_IMPORT, id="imported_before"),
    ],
)
async def test_flow_import_existing_entry(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    source: str,
) -> None:
    """Test importing YAML for an API key that already has an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Prowl", data=CONF_INPUT, source=source
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_API_KEY: TEST_API_KEY, CONF_NAMES: ["prowl"]},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.title == "Prowl"
    assert entry.data == CONF_INPUT
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_prowlpy.verify_key.assert_not_called()
