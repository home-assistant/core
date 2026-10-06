"""Test Prowl config flow."""

from typing import Any
from unittest.mock import AsyncMock

import prowlpy
import pytest

from homeassistant import config_entries
from homeassistant.components.prowl.const import CONF_LEGACY_SERVICE_NAMES, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    BAD_API_RESPONSE,
    CONF_INPUT,
    INVALID_API_KEY_ERROR,
    OTHER_API_KEY,
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


@pytest.mark.parametrize(
    ("import_data", "expected_title", "expected_legacy_service_name"),
    [
        pytest.param(
            {CONF_API_KEY: TEST_API_KEY, CONF_NAME: "My Prowl"},
            "My Prowl",
            "My Prowl",
            id="with_name",
        ),
        pytest.param({CONF_API_KEY: TEST_API_KEY}, "Prowl", None, id="without_name"),
    ],
)
@pytest.mark.usefixtures("mock_prowlpy")
async def test_flow_import(
    hass: HomeAssistant,
    import_data: dict[str, str],
    expected_title: str,
    expected_legacy_service_name: str | None,
) -> None:
    """Test importing a YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=import_data,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {
        CONF_API_KEY: TEST_API_KEY,
        CONF_LEGACY_SERVICE_NAMES: [expected_legacy_service_name],
    }


@pytest.mark.parametrize(
    ("entry_data", "expected_names"),
    [
        pytest.param(CONF_INPUT, ["prowl"], id="set_up_in_ui"),
        pytest.param(
            {**CONF_INPUT, CONF_LEGACY_SERVICE_NAMES: [None, "other"]},
            [None, "other", "prowl"],
            id="other_yaml_names",
        ),
    ],
)
@pytest.mark.usefixtures("mock_prowlpy")
async def test_flow_import_existing_entry(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    expected_names: list[str | None],
) -> None:
    """Test importing YAML for an API key that already has an entry."""
    MockConfigEntry(
        domain=DOMAIN, title="Other", data={CONF_API_KEY: OTHER_API_KEY}
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Prowl",
        data=entry_data,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_API_KEY: TEST_API_KEY, CONF_NAME: "prowl"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {
        CONF_API_KEY: TEST_API_KEY,
        CONF_LEGACY_SERVICE_NAMES: expected_names,
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_flow_import_already_imported(
    hass: HomeAssistant, mock_prowlpy: AsyncMock
) -> None:
    """Test importing YAML that was imported before."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="prowl",
        data={CONF_API_KEY: TEST_API_KEY, CONF_LEGACY_SERVICE_NAMES: [None, "prowl"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_API_KEY: TEST_API_KEY, CONF_NAME: "prowl"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_prowlpy.verify_key.assert_not_called()
