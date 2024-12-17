"""Test the Bosch SHC config flow."""

from ipaddress import ip_address
from unittest.mock import PropertyMock, mock_open, patch

from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCRegistrationError,
    SHCSessionError,
)
from boschshcpy.information import SHCInformation
import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.bosch_shc.config_flow import write_tls_asset
from homeassistant.components.bosch_shc.const import CONF_SHC_CERT, CONF_SHC_KEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_SETTINGS = {
    "name": "Test name",
    "device": {"mac": "test-mac", "hostname": "test-host"},
}
DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="shc012345.local.",
    name="Bosch SHC [test-mac]._http._tcp.local.",
    port=0,
    properties={},
    type="_http._tcp.local.",
)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch("boschshcpy.session.SHCSession.authenticate") as mock_authenticate,
        patch(
            "homeassistant.components.bosch_shc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "shc012345"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": hass.config.path(DOMAIN, "test-mac", CONF_SHC_CERT),
        "ssl_key": hass.config.path(DOMAIN, "test-mac", CONF_SHC_KEY),
        "token": "abc:123",
        "hostname": "123",
    }

    assert len(mock_authenticate.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_get_info_connection_error(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        side_effect=SHCConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_get_info_exception(hass: HomeAssistant) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_pairing_error(hass: HomeAssistant) -> None:
    """Test we handle pairing error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        side_effect=SHCRegistrationError(""),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "pairing_failed"}


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch(
            "boschshcpy.session.SHCSession.authenticate",
            side_effect=SHCAuthenticationError,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "invalid_auth"}


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_validate_connection_error(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch(
            "boschshcpy.session.SHCSession.authenticate",
            side_effect=SHCConnectionError,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_validate_session_error(hass: HomeAssistant) -> None:
    """Test we handle session error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch(
            "boschshcpy.session.SHCSession.authenticate",
            side_effect=SHCSessionError(""),
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "session_error"}


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_validate_exception(hass: HomeAssistant) -> None:
    """Test we handle exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch(
            "boschshcpy.session.SHCSession.authenticate",
            side_effect=Exception,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mock_zeroconf")
async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="bosch_shc", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_discovery"
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shc012345"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch(
            "boschshcpy.session.SHCSession.authenticate",
        ),
        patch(
            "homeassistant.components.bosch_shc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "shc012345"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": hass.config.path(DOMAIN, "test-mac", CONF_SHC_CERT),
        "ssl_key": hass.config.path(DOMAIN, "test-mac", CONF_SHC_KEY),
        "token": "abc:123",
        "hostname": "123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_zeroconf")
async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="bosch_shc", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "boschshcpy.session.SHCSession.mdns_info", side_effect=SHCConnectionError
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_zeroconf_not_bosch_shc(hass: HomeAssistant) -> None:
    """Test we filter out non-bosch_shc devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="mock_hostname",
            name="notboschshc",
            port=None,
            properties={},
            type="mock_type",
        ),
        context={"source": config_entries.SOURCE_ZEROCONF},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_bosch_shc"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_reauth(hass: HomeAssistant) -> None:
    """Test we get the form."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-mac",
        data={
            "host": "1.1.1.1",
            "hostname": "test-mac",
            "ssl_certificate": "test-cert.pem",
            "ssl_key": "test-key.pem",
        },
        title="shc012345",
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value="shc012345",
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value="test-mac",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "2.2.2.2"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "credentials"
        assert result2["errors"] == {}

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value={
                "token": "abc:123",
                "cert": b"content_cert",
                "key": b"content_key",
            },
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch("boschshcpy.session.SHCSession.authenticate"),
        patch(
            "homeassistant.components.bosch_shc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"

    assert mock_config.data["host"] == "2.2.2.2"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_tls_assets_writer(hass: HomeAssistant) -> None:
    """Test we write tls assets to correct location."""
    unique_id = "test-mac"
    assets = {
        "token": "abc:123",
        "cert": b"content_cert",
        "key": b"content_key",
    }
    with (
        patch("os.mkdir"),
        patch(
            "homeassistant.components.bosch_shc.config_flow.open", mock_open()
        ) as mocked_file,
    ):
        write_tls_asset(hass, unique_id, CONF_SHC_CERT, assets["cert"])
        mocked_file.assert_called_with(
            hass.config.path(DOMAIN, unique_id, CONF_SHC_CERT), "w", encoding="utf8"
        )
        mocked_file().write.assert_called_with("content_cert")

        write_tls_asset(hass, unique_id, CONF_SHC_KEY, assets["key"])
        mocked_file.assert_called_with(
            hass.config.path(DOMAIN, unique_id, CONF_SHC_KEY), "w", encoding="utf8"
        )
        mocked_file().write.assert_called_with("content_key")


@pytest.mark.usefixtures("mock_zeroconf")
async def test_register_multiple_controllers(hass: HomeAssistant) -> None:
    """Test register multiple controllers.

    Each registered controller must get its own key/certificate pair,
    which must not get overwritten when a new controller is added.
    """

    controller_1 = {
        "hostname": "shc111111",
        "mac": "test-mac1",
        "host": "1.1.1.1",
        "register": {
            "token": "abc:shc111111",
            "cert": b"content_cert1",
            "key": b"content_key1",
        },
    }
    controller_2 = {
        "hostname": "shc222222",
        "mac": "test-mac2",
        "host": "2.2.2.2",
        "register": {
            "token": "abc:shc222222",
            "cert": b"content_cert2",
            "key": b"content_key2",
        },
    }

    # Set up controller 1
    ctrl_1_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value=controller_1["hostname"],
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value=controller_1["mac"],
        ),
    ):
        ctrl_1_result2 = await hass.config_entries.flow.async_configure(
            ctrl_1_result["flow_id"],
            {"host": controller_1["host"]},
        )

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value=controller_1["register"],
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch("boschshcpy.session.SHCSession.authenticate"),
        patch(
            "homeassistant.components.bosch_shc.async_setup_entry",
            return_value=True,
        ),
    ):
        ctrl_1_result3 = await hass.config_entries.flow.async_configure(
            ctrl_1_result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert ctrl_1_result3["type"] is FlowResultType.CREATE_ENTRY
    assert ctrl_1_result3["title"] == "shc111111"
    assert ctrl_1_result3["context"]["unique_id"] == controller_1["mac"]
    assert ctrl_1_result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": hass.config.path(DOMAIN, controller_1["mac"], CONF_SHC_CERT),
        "ssl_key": hass.config.path(DOMAIN, controller_1["mac"], CONF_SHC_KEY),
        "token": "abc:shc111111",
        "hostname": "shc111111",
    }

    # Set up controller 2
    ctrl_2_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "boschshcpy.session.SHCSession.mdns_info",
            return_value=SHCInformation,
        ),
        patch(
            "boschshcpy.information.SHCInformation.name",
            new_callable=PropertyMock,
            return_value=controller_2["hostname"],
        ),
        patch(
            "boschshcpy.information.SHCInformation.unique_id",
            new_callable=PropertyMock,
            return_value=controller_2["mac"],
        ),
    ):
        ctrl_2_result2 = await hass.config_entries.flow.async_configure(
            ctrl_2_result["flow_id"],
            {"host": controller_2["host"]},
        )

    with (
        patch(
            "boschshcpy.register_client.SHCRegisterClient.register",
            return_value=controller_2["register"],
        ),
        patch("os.mkdir"),
        patch("homeassistant.components.bosch_shc.config_flow.open"),
        patch("boschshcpy.session.SHCSession.authenticate"),
        patch(
            "homeassistant.components.bosch_shc.async_setup_entry",
            return_value=True,
        ),
    ):
        ctrl_2_result3 = await hass.config_entries.flow.async_configure(
            ctrl_2_result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert ctrl_2_result3["type"] is FlowResultType.CREATE_ENTRY
    assert ctrl_2_result3["title"] == "shc222222"
    assert ctrl_2_result3["context"]["unique_id"] == controller_2["mac"]
    assert ctrl_2_result3["data"] == {
        "host": "2.2.2.2",
        "ssl_certificate": hass.config.path(DOMAIN, controller_2["mac"], CONF_SHC_CERT),
        "ssl_key": hass.config.path(DOMAIN, controller_2["mac"], CONF_SHC_KEY),
        "token": "abc:shc222222",
        "hostname": "shc222222",
    }

    # Check that each controller has its own key/certificate pair
    assert (
        ctrl_1_result3["data"]["ssl_certificate"]
        != ctrl_2_result3["data"]["ssl_certificate"]
    )
    assert ctrl_1_result3["data"]["ssl_key"] != ctrl_2_result3["data"]["ssl_key"]
