"""Test the Clicky Web Analytics config flow."""

from unittest.mock import AsyncMock, patch

from pyclicky import AuthenticationError, ClickyAPIError, ConnectionError

from homeassistant import config_entries
from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_SITE_ID, TEST_SITEKEY

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ):
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

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient",
        autospec=True,
    ) as mock_lib:
        client = mock_lib.return_value
        client.visitors_online.side_effect = Exception

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_duplicate_site_id(hass: HomeAssistant) -> None:
    """Test that duplicate site IDs abort the config flow."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: TEST_SITE_ID,
            CONF_SITEKEY: "different_sitekey",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_authentication_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that AuthenticationError is mapped to invalid_auth."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ) as mock_lib:
        client = mock_lib.return_value
        client.visitors_online.side_effect = AuthenticationError

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_connection_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that ConnectionError is mapped to cannot_connect."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ) as mock_lib:
        client = mock_lib.return_value
        client.visitors_online.side_effect = ConnectionError

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_api_error(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that ClickyAPIError is mapped to unknown."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ) as mock_lib:
        client = mock_lib.return_value
        client.visitors_online.side_effect = ClickyAPIError

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert len(mock_setup_entry.mock_calls) == 0
