"""Test the Duck DNS config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.duckdns.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_SUBDOMAIN, TEST_TOKEN

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_update_duckdns")
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: "123e4567-e89b-12d3-a456-426614174000",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_SUBDOMAIN}.duckdns.org"
    assert result["data"] == {
        CONF_DOMAIN: TEST_SUBDOMAIN,
        CONF_ACCESS_TOKEN: TEST_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_update_duckdns")
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: "123e4567-e89b-12d3-a456-426614174000",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_unknown_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_update_duckdns: AsyncMock,
) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_update_duckdns.side_effect = ValueError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_update_duckdns.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_SUBDOMAIN}.duckdns.org"
    assert result["data"] == {
        CONF_DOMAIN: TEST_SUBDOMAIN,
        CONF_ACCESS_TOKEN: TEST_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_update_failed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_update_duckdns: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_update_duckdns.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "update_failed"}

    mock_update_duckdns.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_SUBDOMAIN}.duckdns.org"
    assert result["data"] == {
        CONF_DOMAIN: TEST_SUBDOMAIN,
        CONF_ACCESS_TOKEN: TEST_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_update_duckdns")
async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test import flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_SUBDOMAIN}.duckdns.org"
    assert result["data"] == {
        CONF_DOMAIN: TEST_SUBDOMAIN,
        CONF_ACCESS_TOKEN: TEST_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


async def test_import_failed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
    mock_update_duckdns: AsyncMock,
) -> None:
    """Test import flow failed."""
    mock_update_duckdns.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "update_failed"

    assert len(mock_setup_entry.mock_calls) == 0

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_yaml_import_issue_error",
    )


async def test_import_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
    mock_update_duckdns: AsyncMock,
) -> None:
    """Test import flow failed unknown."""
    mock_update_duckdns.side_effect = ValueError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"

    assert len(mock_setup_entry.mock_calls) == 0

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_yaml_import_issue_error",
    )


@pytest.mark.usefixtures("mock_update_duckdns")
async def test_init_import_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test yaml triggers import flow."""

    await async_setup_component(
        hass,
        DOMAIN,
        {"duckdns": {CONF_DOMAIN: TEST_SUBDOMAIN, CONF_ACCESS_TOKEN: TEST_TOKEN}},
    )
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
