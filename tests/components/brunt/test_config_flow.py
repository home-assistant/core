"""Test the Brunt config flow."""
from unittest.mock import patch

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ServerDisconnectedError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.brunt.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

CONF = {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}


async def _flow_submit(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONF,
    )


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch("brunt.BruntClientAsync.async_login", return_value=True), patch(
        "homeassistant.components.brunt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == CONF
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("brunt.BruntClientAsync.async_login", return_value=True), patch(
        "homeassistant.components.brunt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONF,
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == CONF
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_duplicate_login(hass):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="test-username",
        unique_id="test-username",
    )
    with patch("brunt.BruntClientAsync.async_login", return_value=True), patch(
        "homeassistant.components.brunt.async_setup_entry",
        return_value=True,
    ):
        entry.add_to_hass(hass)
        # with patch("brunt.BruntClientAsync.async_login", return_value=True)
        # , patch(
        #     "homeassistant.components.brunt.async_setup_entry",
        #     return_value=True,
        # ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONF,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_form_duplicate_login(hass):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="test-username",
        unique_id="test-username",
    )
    with patch("brunt.BruntClientAsync.async_login", return_value=True):
        entry.add_to_hass(hass)
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    with patch(
        "brunt.BruntClientAsync.async_login",
        side_effect=ClientResponseError(None, None, status=403),
    ):
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect."""
    with patch(
        "brunt.BruntClientAsync.async_login",
        side_effect=ServerDisconnectedError,
    ):
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_client_response_unknown(hass):
    """Test we handle invalid auth."""
    with patch(
        "brunt.BruntClientAsync.async_login",
        side_effect=ClientResponseError(None, None, status=401),
    ), patch(
        "aiohttp.client_exceptions.ClientResponseError.__str__",
        return_value="ClientResponseError",
    ):
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}


async def test_form_generic_exception(hass):
    """Test we handle cannot connect error."""
    with patch(
        "brunt.BruntClientAsync.async_login",
        side_effect=Exception,
    ):
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}


async def test_reauth(hass):
    """Test uniqueness of username."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="test-username",
        unique_id="test-username",
    )
    with patch(
        "brunt.BruntClientAsync.async_login",
        side_effect=ClientResponseError(None, None, status=403),
    ):
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": entry.unique_id,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
    with patch("brunt.BruntClientAsync.async_login", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"username": "test-username", "password": "test"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data["username"] == "test-username"
        assert entry.data["password"] == "test"
