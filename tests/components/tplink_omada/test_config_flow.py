"""Test the TP-Link Omada config flows."""
from unittest.mock import patch

from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)
from tplink_omada_client.omadaclient import OmadaSite

from homeassistant import config_entries
from homeassistant.components.tplink_omada.config_flow import (
    HubInfo,
    _validate_input,
    create_omada_client,
)
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USER_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "username": "test-username",
    "password": "test-password",
}

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


async def test_form_single_site(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        return_value=HubInfo(
            "omada_id", "OC200", [OmadaSite("Display Name", "SiteId")]
        ),
    ) as mocked_validate, patch(
        "homeassistant.components.tplink_omada.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "OC200 (Display Name)"
    assert result2["data"] == MOCK_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1
    mocked_validate.assert_called_once_with(hass, MOCK_USER_DATA)


async def test_form_multiple_sites(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        return_value=HubInfo(
            "omada_id",
            "OC200",
            [OmadaSite("Site 1", "first"), OmadaSite("Site 2", "second")],
        ),
    ), patch(
        "homeassistant.components.tplink_omada.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "site"

    with patch(
        "homeassistant.components.tplink_omada.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "site": "second",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "OC200 (Site 2)"
    assert result3["data"] == {
        "host": "https://fake.omada.host",
        "verify_ssl": True,
        "site": "second",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=LoginFailed(-1000, "Invalid username/password"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_api_error(hass: HomeAssistant) -> None:
    """Test we handle unknown API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=OmadaClientException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_generic_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_unsupported_controller(hass: HomeAssistant) -> None:
    """Test we handle unknown API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=UnsupportedControllerVersion("4.0.0"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unsupported_controller"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=ConnectionFailed,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_sites(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        return_value=HubInfo("omada_id", "OC200", []),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "no_sites_found"}


async def test_async_step_reauth_success(hass: HomeAssistant) -> None:
    """Test reauth starts an interactive flow."""

    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        return_value=HubInfo(
            "omada_id", "OC200", [OmadaSite("Display Name", "SiteId")]
        ),
    ) as mocked_validate:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "new_uname", "password": "new_passwd"}
        )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    mocked_validate.assert_called_once_with(
        hass,
        {
            "host": "https://fake.omada.host",
            "verify_ssl": True,
            "site": "SiteId",
            "username": "new_uname",
            "password": "new_passwd",
        },
    )


async def test_async_step_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauth starts an interactive flow."""

    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=LoginFailed(-1000, "Invalid username/password"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "new_uname", "password": "new_passwd"}
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_validate_input(hass: HomeAssistant) -> None:
    """Test validate returns HubInfo."""

    with patch(
        "tplink_omada_client.omadaclient.OmadaClient", autospec=True
    ) as mock_client, patch(
        "homeassistant.components.tplink_omada.config_flow.create_omada_client",
        return_value=mock_client,
    ) as create_mock:
        mock_client.login.return_value = "Id"
        mock_client.get_controller_name.return_value = "Name"
        mock_client.get_sites.return_value = [OmadaSite("x", "y")]
        result = await _validate_input(hass, MOCK_USER_DATA)

    create_mock.assert_awaited_once()
    mock_client.login.assert_awaited_once()
    mock_client.get_controller_name.assert_awaited_once()
    mock_client.get_sites.assert_awaited_once()
    assert result.controller_id == "Id"
    assert result.name == "Name"
    assert result.sites == [OmadaSite("x", "y")]


async def test_create_omada_client_parses_args(hass: HomeAssistant) -> None:
    """Test config arguments are passed to Omada client."""

    with patch(
        "homeassistant.components.tplink_omada.config_flow.OmadaClient", autospec=True
    ) as mock_client, patch(
        "homeassistant.components.tplink_omada.config_flow.async_get_clientsession",
        return_value="ws",
    ) as mock_clientsession:
        result = await create_omada_client(hass, MOCK_USER_DATA)

    assert result is not None
    mock_client.assert_called_once_with(
        "https://fake.omada.host", "test-username", "test-password", "ws"
    )
    mock_clientsession.assert_called_once_with(hass, verify_ssl=True)


async def test_create_omada_client_adds_missing_scheme(hass: HomeAssistant) -> None:
    """Test config arguments are passed to Omada client."""

    with patch(
        "homeassistant.components.tplink_omada.config_flow.OmadaClient", autospec=True
    ) as mock_client, patch(
        "homeassistant.components.tplink_omada.config_flow.async_get_clientsession",
        return_value="ws",
    ) as mock_clientsession:
        result = await create_omada_client(
            hass,
            {
                "host": "fake.omada.host",
                "verify_ssl": True,
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result is not None
    mock_client.assert_called_once_with(
        "https://fake.omada.host", "test-username", "test-password", "ws"
    )
    mock_clientsession.assert_called_once_with(hass, verify_ssl=True)


async def test_create_omada_client_with_ip_creates_clientsession(
    hass: HomeAssistant,
) -> None:
    """Test config arguments are passed to Omada client."""

    with patch(
        "homeassistant.components.tplink_omada.config_flow.OmadaClient", autospec=True
    ) as mock_client, patch(
        "homeassistant.components.tplink_omada.config_flow.CookieJar", autospec=True
    ) as mock_jar, patch(
        "homeassistant.components.tplink_omada.config_flow.async_create_clientsession",
        return_value="ws",
    ) as mock_create_clientsession:
        result = await create_omada_client(
            hass,
            {
                "host": "10.10.10.10",
                "verify_ssl": True,  # Verify is meaningless for IP
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result is not None
    mock_client.assert_called_once_with(
        "https://10.10.10.10", "test-username", "test-password", "ws"
    )
    mock_create_clientsession.assert_called_once_with(
        hass, cookie_jar=mock_jar.return_value
    )
