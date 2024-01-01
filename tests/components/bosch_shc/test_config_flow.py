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

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.bosch_shc.config_flow import write_tls_asset
from homeassistant.components.bosch_shc.const import CONF_SHC_CERT, CONF_SHC_KEY, DOMAIN
from homeassistant.core import HomeAssistant

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


async def test_form_user(hass: HomeAssistant, mock_zeroconf: None) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate"
    ) as mock_authenticate, patch(
        "homeassistant.components.bosch_shc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "shc012345"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": hass.config.path(DOMAIN, CONF_SHC_CERT),
        "ssl_key": hass.config.path(DOMAIN, CONF_SHC_KEY),
        "token": "abc:123",
        "hostname": "123",
    }

    assert len(mock_authenticate.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_get_info_connection_error(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
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

    assert result2["type"] == "form"
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

    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_pairing_error(hass: HomeAssistant, mock_zeroconf: None) -> None:
    """Test we handle pairing error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
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

    assert result3["type"] == "form"
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "pairing_failed"}


async def test_form_user_invalid_auth(hass: HomeAssistant, mock_zeroconf: None) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=SHCAuthenticationError,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_form_validate_connection_error(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
    """Test we handle connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=SHCConnectionError,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_validate_session_error(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
    """Test we handle session error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=SHCSessionError(""),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "session_error"}


async def test_form_validate_exception(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
    """Test we handle exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "credentials"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=Exception,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["step_id"] == "credentials"
    assert result3["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="bosch_shc", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == "abort"
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_zeroconf(hass: HomeAssistant, mock_zeroconf: None) -> None:
    """Test we get the form."""

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "form"
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
    assert result2["type"] == "form"
    assert result2["step_id"] == "credentials"

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate",
    ), patch(
        "homeassistant.components.bosch_shc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "shc012345"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": hass.config.path(DOMAIN, CONF_SHC_CERT),
        "ssl_key": hass.config.path(DOMAIN, CONF_SHC_KEY),
        "token": "abc:123",
        "hostname": "123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="bosch_shc", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_zeroconf_cannot_connect(
    hass: HomeAssistant, mock_zeroconf: None
) -> None:
    """Test we get the form."""
    with patch(
        "boschshcpy.session.SHCSession.mdns_info", side_effect=SHCConnectionError
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_not_bosch_shc(hass: HomeAssistant, mock_zeroconf: None) -> None:
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
    assert result["type"] == "abort"
    assert result["reason"] == "not_bosch_shc"


async def test_reauth(hass: HomeAssistant, mock_zeroconf: None) -> None:
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
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=mock_config.data,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.unique_id",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "2.2.2.2"},
        )

        assert result2["type"] == "form"
        assert result2["step_id"] == "credentials"
        assert result2["errors"] == {}

    with patch(
        "boschshcpy.register_client.SHCRegisterClient.register",
        return_value={
            "token": "abc:123",
            "cert": b"content_cert",
            "key": b"content_key",
        },
    ), patch("os.mkdir"), patch("builtins.open"), patch(
        "boschshcpy.session.SHCSession.authenticate"
    ), patch(
        "homeassistant.components.bosch_shc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "reauth_successful"

    assert mock_config.data["host"] == "2.2.2.2"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_tls_assets_writer(hass: HomeAssistant) -> None:
    """Test we write tls assets to correct location."""
    assets = {
        "token": "abc:123",
        "cert": b"content_cert",
        "key": b"content_key",
    }
    with patch("os.mkdir"), patch("builtins.open", mock_open()) as mocked_file:
        write_tls_asset(hass, CONF_SHC_CERT, assets["cert"])
        mocked_file.assert_called_with(
            hass.config.path(DOMAIN, CONF_SHC_CERT), "w", encoding="utf8"
        )
        mocked_file().write.assert_called_with("content_cert")

        write_tls_asset(hass, CONF_SHC_KEY, assets["key"])
        mocked_file.assert_called_with(
            hass.config.path(DOMAIN, CONF_SHC_KEY), "w", encoding="utf8"
        )
        mocked_file().write.assert_called_with("content_key")
