"""Test the Free Mobile config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


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
    assert result["title"] == MOCK_CONFIG[CONF_USERNAME]
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


async def test_flow_import_dedup_by_title_same_name_is_rejected(
    hass: HomeAssistant,
) -> None:
    """Test importing the same title twice is rejected, even with a shared username."""
    first_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=first_import
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maman"

    second_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=second_import
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import_dedup_by_title_distinct_name_allows_shared_username(
    hass: HomeAssistant,
) -> None:
    """Test a distinct name allows importing a shared username.

    This preserves legacy multi-account YAML setups where several named
    notify services share the same Free Mobile username.
    """
    first_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=first_import
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maman"

    second_import = {**MOCK_CONFIG, CONF_NAME: "Papa"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=second_import
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Papa"


async def test_flow_import_no_name_uses_username_as_title(hass: HomeAssistant) -> None:
    """Test import without a name falls back to the username as title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_USERNAME]
    assert result["data"] == MOCK_CONFIG
