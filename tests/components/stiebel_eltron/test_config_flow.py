"""Test the STIEBEL ELTRON config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_stiebel_eltron_client")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stiebel Eltron"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 502,
    }


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_stiebel_eltron_client.update.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_stiebel_eltron_client.update.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unknown_exception(
    hass: HomeAssistant,
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_stiebel_eltron_client.update.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_stiebel_eltron_client.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_stiebel_eltron_client")
async def test_import(hass: HomeAssistant) -> None:
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
            CONF_NAME: "Stiebel Eltron",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stiebel Eltron"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 502,
    }


async def test_import_cannot_connect(
    hass: HomeAssistant,
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_stiebel_eltron_client.update.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
            CONF_NAME: "Stiebel Eltron",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_unknown_exception(
    hass: HomeAssistant,
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_stiebel_eltron_client.update.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
            CONF_NAME: "Stiebel Eltron",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
            CONF_NAME: "Stiebel Eltron",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
