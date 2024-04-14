"""Test the TP-Link Omada config flows."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from tplink_omada_client import OmadaSite
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant import config_entries
from homeassistant.components.tplink_omada.config_flow import (
    OPT_DEVICE_TRACKER,
    OPT_SCANNED_CLIENTS,
    OPT_TRACKED_CLIENTS,
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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow._validate_input",
            return_value=HubInfo(
                "omada_id", "OC200", [OmadaSite("Display Name", "SiteId")]
            ),
        ) as mocked_validate,
        patch(
            "homeassistant.components.tplink_omada.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "OC200 (Display Name)"
    assert result2["data"] == MOCK_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1
    mocked_validate.assert_called_once_with(hass, MOCK_USER_DATA)


async def test_form_multiple_sites(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow._validate_input",
            return_value=HubInfo(
                "omada_id",
                "OC200",
                [OmadaSite("Site 1", "first"), OmadaSite("Site 2", "second")],
            ),
        ),
        patch(
            "homeassistant.components.tplink_omada.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
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

    assert result3["type"] is FlowResultType.CREATE_ENTRY
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.tplink_omada.config_flow._validate_input",
        side_effect=LoginFailed(-1000, "Invalid username/password"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "new_uname", "password": "new_passwd"}
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_validate_input(hass: HomeAssistant) -> None:
    """Test validate returns HubInfo."""

    with (
        patch(
            "tplink_omada_client.omadaclient.OmadaClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.create_omada_client",
            return_value=mock_client,
        ) as create_mock,
    ):
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

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow.OmadaClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.async_get_clientsession",
            return_value="ws",
        ) as mock_clientsession,
    ):
        result = await create_omada_client(hass, MOCK_USER_DATA)

    assert result is not None
    mock_client.assert_called_once_with(
        "https://fake.omada.host", "test-username", "test-password", "ws"
    )
    mock_clientsession.assert_called_once_with(hass, verify_ssl=True)


async def test_create_omada_client_adds_missing_scheme(hass: HomeAssistant) -> None:
    """Test config arguments are passed to Omada client."""

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow.OmadaClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.async_get_clientsession",
            return_value="ws",
        ) as mock_clientsession,
    ):
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

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow.OmadaClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.CookieJar", autospec=True
        ) as mock_jar,
        patch(
            "homeassistant.components.tplink_omada.config_flow.async_create_clientsession",
            return_value="ws",
        ) as mock_create_clientsession,
    ):
        result = await create_omada_client(
            hass,
            {
                "host": "10.10.10.10",
                "verify_ssl": True,
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result is not None
    mock_client.assert_called_once_with(
        "https://10.10.10.10", "test-username", "test-password", "ws"
    )
    mock_create_clientsession.assert_called_once_with(
        hass, cookie_jar=mock_jar.return_value, verify_ssl=True
    )


async def test_first_options_flow_with_no_tracker_creates_options(
    hass: HomeAssistant,
) -> None:
    """Test we get the initial form if there are no Options configured."""
    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={OPT_DEVICE_TRACKER: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {OPT_DEVICE_TRACKER: False}


async def test_options_flow_defaults_form_with_selected_option(
    hass: HomeAssistant,
) -> None:
    """Test we get the initial form with pre-filled options."""
    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        options={OPT_DEVICE_TRACKER: True},
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert _get_schema_default(result["data_schema"].schema, OPT_DEVICE_TRACKER) is True
    assert result["step_id"] == "init"
    assert result["errors"] is None


def _get_schema_default(schema, key_name):
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


async def test_options_flow_enable_device_tracker_gets_known_clients(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_omada_clients_only_site_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that if the device tracker is enabled, we get a populated device tracker form."""
    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        options={OPT_DEVICE_TRACKER: False},
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={OPT_DEVICE_TRACKER: True}
    )

    mock_omada_clients_only_site_client.get_known_clients.assert_called_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_tracker"
    schema = result["data_schema"].schema[OPT_TRACKED_CLIENTS]
    assert schema.config == snapshot


async def test_options_flow_enable_device_tracker_no_clients_selected_returns_error(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_omada_clients_only_site_client: MagicMock,
) -> None:
    """Test that if the user doesn't select any devices to track, they are given an error message."""
    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        options={OPT_DEVICE_TRACKER: False},
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={OPT_DEVICE_TRACKER: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_tracker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPT_TRACKED_CLIENTS: [],
            OPT_SCANNED_CLIENTS: [],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_tracker"
    assert result["errors"] == {OPT_TRACKED_CLIENTS: "no_clients_selected"}


async def test_options_flow_enable_device_tracker_creates_entry(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_omada_clients_only_site_client: MagicMock,
) -> None:
    """Test the options flow allows selection of tracked and scanned devices by Mac."""
    mock_entry = MockConfigEntry(
        domain="tplink_omada",
        data=dict(MOCK_ENTRY_DATA),
        options={OPT_DEVICE_TRACKER: False},
        unique_id="USERID",
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={OPT_DEVICE_TRACKER: True}
    )

    mock_omada_clients_only_site_client.get_known_clients.assert_called_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_tracker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPT_TRACKED_CLIENTS: ["2E-DC-E1-C4-37-D3"],
            OPT_SCANNED_CLIENTS: ["2C-71-FF-ED-34-83"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {
        OPT_DEVICE_TRACKER: True,
        OPT_TRACKED_CLIENTS: ["2E-DC-E1-C4-37-D3"],
        OPT_SCANNED_CLIENTS: ["2C-71-FF-ED-34-83"],
    }
