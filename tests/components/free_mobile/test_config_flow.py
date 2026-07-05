"""Test the Free Mobile config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


def _suggested_value(data_schema: vol.Schema | None, key: str) -> Any:
    """Return the suggested value for a schema key, if any."""
    assert data_schema is not None
    for schema_key in data_schema.schema:
        if schema_key == key:
            return schema_key.description["suggested_value"]
    raise KeyError(key)


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.free_mobile.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow creates an entry titled after the username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DOMAIN}_{MOCK_CONFIG[CONF_USERNAME]}"
    assert result["data"] == MOCK_CONFIG


async def test_flow_user_username_already_configured(hass: HomeAssistant) -> None:
    """Test the user flow aborts if the username is already configured."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MOCK_CONFIG, CONF_ACCESS_TOKEN: "another-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("second_name", "expected_type", "expected_reason"),
    [
        pytest.param(
            "Maman",
            FlowResultType.ABORT,
            "already_configured",
            id="same_name_is_rejected",
        ),
        pytest.param(
            "Papa",
            FlowResultType.CREATE_ENTRY,
            None,
            id="distinct_name_allows_shared_username",
        ),
    ],
)
async def test_flow_import_dedup_by_title(
    hass: HomeAssistant,
    second_name: str,
    expected_type: FlowResultType,
    expected_reason: str | None,
) -> None:
    """Test import dedup by title.

    A shared username with a distinct name (legacy multi-account YAML
    setups) is still allowed.
    """
    first_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=first_import
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maman"

    second_import = {**MOCK_CONFIG, CONF_NAME: second_name}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=second_import
    )

    assert result["type"] is expected_type
    if expected_reason is not None:
        assert result["reason"] == expected_reason
    else:
        assert result["title"] == second_name


async def test_flow_import_no_name_uses_username_as_title(hass: HomeAssistant) -> None:
    """Test import without a name falls back to the username as title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_USERNAME]
    assert result["data"] == MOCK_CONFIG


async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Test the reconfigure flow updates the access token."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert (
        _suggested_value(result["data_schema"], CONF_ACCESS_TOKEN)
        == MOCK_CONFIG[CONF_ACCESS_TOKEN]
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {**MOCK_CONFIG, CONF_ACCESS_TOKEN: "new-token"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test the reauth flow updates the access token."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert (
        _suggested_value(result["data_schema"], CONF_ACCESS_TOKEN)
        == MOCK_CONFIG[CONF_ACCESS_TOKEN]
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {**MOCK_CONFIG, CONF_ACCESS_TOKEN: "new-token"}
