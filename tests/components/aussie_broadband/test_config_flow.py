"""Test the Aussie Broadband config flow."""
from unittest.mock import patch

from aiohttp import ClientConnectionError
from aussiebb.asyncio import AuthenticationException

from homeassistant import config_entries, setup
from homeassistant.components.aussie_broadband.const import CONF_SERVICES, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .common import FAKE_DATA, FAKE_SERVICES, setup_platform

TEST_USERNAME = FAKE_DATA[CONF_USERNAME]
TEST_PASSWORD = FAKE_DATA[CONF_PASSWORD]


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == RESULT_TYPE_FORM
    assert result1["errors"] is None

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch(
        "aussiebb.asyncio.AussieBB.get_services", return_value=[FAKE_SERVICES[0]]
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            FAKE_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == TEST_USERNAME
    assert result2["data"] == FAKE_DATA
    assert result2["options"] == {CONF_SERVICES: ["12345678"]}
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

    assert result4["type"] == RESULT_TYPE_ABORT
    assert len(mock_setup_entry.mock_calls) == 0


async def test_no_services(hass: HomeAssistant) -> None:
    """Test when there are no services."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == RESULT_TYPE_FORM
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

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "no_services_found"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_multiple_services(hass: HomeAssistant) -> None:
    """Test the config flow with multiple services."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch("aussiebb.asyncio.AussieBB.__init__", return_value=None), patch(
        "aussiebb.asyncio.AussieBB.login", return_value=True
    ), patch("aussiebb.asyncio.AussieBB.get_services", return_value=FAKE_SERVICES):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FAKE_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "service"
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERVICES: [FAKE_SERVICES[1]["service_id"]]},
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == TEST_USERNAME
    assert result3["data"] == FAKE_DATA
    assert result3["options"] == {
        CONF_SERVICES: [FAKE_SERVICES[1]["service_id"]],
    }
    assert len(mock_setup_entry.mock_calls) == 1


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

    assert result2["type"] == RESULT_TYPE_FORM
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

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""

    await setup.async_setup_component(hass, "persistent_notification", {})

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

        assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result2["title"] == TEST_USERNAME
        assert result2["data"] == FAKE_DATA

    # Test failed reauth
    result5 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=FAKE_DATA,
    )
    assert result5["step_id"] == "reauth"

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

        assert result6["step_id"] == "reauth"

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


async def test_options_flow(hass):
    """Test options flow."""
    entry = await setup_platform(hass)

    with patch("aussiebb.asyncio.AussieBB.get_services", return_value=FAKE_SERVICES):

        result1 = await hass.config_entries.options.async_init(entry.entry_id)
        assert result1["type"] == RESULT_TYPE_FORM
        assert result1["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result1["flow_id"],
            user_input={CONF_SERVICES: []},
        )
        assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
        assert entry.options == {CONF_SERVICES: []}


async def test_options_flow_auth_failure(hass):
    """Test options flow with auth failure."""

    entry = await setup_platform(hass)

    with patch(
        "aussiebb.asyncio.AussieBB.get_services", side_effect=AuthenticationException()
    ):

        result1 = await hass.config_entries.options.async_init(entry.entry_id)
        assert result1["type"] == RESULT_TYPE_ABORT
        assert result1["reason"] == "invalid_auth"


async def test_options_flow_network_failure(hass):
    """Test options flow with connectivity failure."""

    entry = await setup_platform(hass)

    with patch(
        "aussiebb.asyncio.AussieBB.get_services", side_effect=ClientConnectionError()
    ):

        result1 = await hass.config_entries.options.async_init(entry.entry_id)
        assert result1["type"] == RESULT_TYPE_ABORT
        assert result1["reason"] == "cannot_connect"


async def test_options_flow_not_loaded(hass):
    """Test the options flow aborts when the entry has unloaded due to a reauth."""

    entry = await setup_platform(hass)

    with patch(
        "aussiebb.asyncio.AussieBB.get_services", side_effect=AuthenticationException()
    ):
        entry.state = config_entries.ConfigEntryState.NOT_LOADED
        result1 = await hass.config_entries.options.async_init(entry.entry_id)
        assert result1["type"] == RESULT_TYPE_ABORT
        assert result1["reason"] == "unknown"
