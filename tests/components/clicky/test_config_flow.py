"""Test the Clicky Web Analytics config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.clicky.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_SITE_ID, TEST_SITEKEY


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    client = AsyncMock()

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_ID
    assert result["data"] == {
        CONF_SITE_ID: TEST_SITE_ID,
        CONF_SITEKEY: TEST_SITEKEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    client = AsyncMock()

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
        side_effect=InvalidAuth,
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_ID
    assert result["data"] == {
        CONF_SITE_ID: TEST_SITE_ID,
        CONF_SITEKEY: TEST_SITEKEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    client = AsyncMock()

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
        side_effect=CannotConnect,
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_ID
    assert result["data"] == {
        CONF_SITE_ID: TEST_SITE_ID,
        CONF_SITEKEY: TEST_SITEKEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    client = AsyncMock()

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
        side_effect=Exception,
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
    ) as mock_lib:
        client = mock_lib.return_value
        client.query = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_ID
    assert result["data"] == {
        CONF_SITE_ID: TEST_SITE_ID,
        CONF_SITEKEY: TEST_SITEKEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1
