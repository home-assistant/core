"""Test the Aussie Broadband config flow."""
from unittest.mock import patch

from aiohttp import ClientConnectionError
from aussiebb.asyncio import AuthenticationException

from homeassistant import config_entries
from homeassistant.components.aussie_broadband.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import FAKE_DATA, FAKE_SERVICES

TEST_USERNAME = FAKE_DATA[CONF_USERNAME]
TEST_PASSWORD = FAKE_DATA[CONF_PASSWORD]


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["errors"] is None

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch(
        "aussiebb.asyncio.AussieBB.get_services", return_value=FAKE_SERVICES
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            FAKE_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USERNAME
    assert result2["data"] == FAKE_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test already configured."""
    # Setup an entry
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch(
        "aussiebb.asyncio.AussieBB.get_services", return_value=[FAKE_SERVICES[0]]
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            FAKE_DATA,
        )
        await hass.async_block_till_done()

    # Test Already configured
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch(
        "aussiebb.asyncio.AussieBB.get_services", return_value=[FAKE_SERVICES[0]]
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            FAKE_DATA,
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.ABORT
    assert len(mock_setup_entry.mock_calls) == 0


async def test_no_services(hass: HomeAssistant) -> None:
    """Test when there are no services."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["errors"] is None

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch("aussiebb.asyncio.AussieBB.get_services", return_value=[]), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            FAKE_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_services_found"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth is handled."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", side_effect=AuthenticationException()
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            FAKE_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_network_issue(hass: HomeAssistant) -> None:
    """Test network issues are handled."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", side_effect=ClientConnectionError()
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            FAKE_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""

    # Test reauth but the entry doesn't exist
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=FAKE_DATA
    )

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch(
        "aussiebb.asyncio.AussieBB.get_services", return_value=[FAKE_SERVICES[0]]
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_USERNAME
        assert result2["data"] == FAKE_DATA

    # Test failed reauth
    result5 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=FAKE_DATA,
    )
    assert result5["step_id"] == "reauth_confirm"

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", side_effect=AuthenticationException()
    ), patch("aussiebb.asyncio.AussieBB.get_services", return_value=[FAKE_SERVICES[0]]):

        result6 = await hass.config_entries.flow.async_configure(
            result5["flow_id"],
            {
                CONF_PASSWORD: "test-wrongpassword",
            },
        )
        await hass.async_block_till_done()

        assert result6["step_id"] == "reauth_confirm"

    # Test successful reauth
    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch("aussiebb.asyncio.AussieBB.get_services", return_value=[FAKE_SERVICES[0]]):

        result7 = await hass.config_entries.flow.async_configure(
            result6["flow_id"],
            {
                CONF_PASSWORD: "test-newpassword",
            },
        )
        await hass.async_block_till_done()

        assert result7["type"] == "abort"
        assert result7["reason"] == "reauth_successful"
