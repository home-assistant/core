"""Test the StreamLabs config flow."""
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.streamlabswater.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch("homeassistant.components.streamlabswater.config_flow.StreamlabsClient"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Streamlabs"
    assert result["data"] == {CONF_API_KEY: "abc"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.streamlabswater.config_flow.StreamlabsClient.get_locations",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "abc"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch("homeassistant.components.streamlabswater.config_flow.StreamlabsClient"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Streamlabs"
    assert result["data"] == {CONF_API_KEY: "abc"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.streamlabswater.config_flow.StreamlabsClient.get_locations",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "abc"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch("homeassistant.components.streamlabswater.config_flow.StreamlabsClient"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Streamlabs"
    assert result["data"] == {CONF_API_KEY: "abc"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_entry_already_exists(hass: HomeAssistant) -> None:
    """Test we handle if the entry already exists."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "abc"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.streamlabswater.config_flow.StreamlabsClient.get_locations",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "abc"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test import flow."""
    with patch("homeassistant.components.streamlabswater.config_flow.StreamlabsClient"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Streamlabs"
    assert result["data"] == {CONF_API_KEY: "abc"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.streamlabswater.config_flow.StreamlabsClient.get_locations",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_unknown(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle unknown error."""
    with patch(
        "homeassistant.components.streamlabswater.config_flow.StreamlabsClient.get_locations",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_entry_already_exists(hass: HomeAssistant) -> None:
    """Test we handle if the entry already exists."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "abc"},
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.streamlabswater.config_flow.StreamlabsClient"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_API_KEY: "abc"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
