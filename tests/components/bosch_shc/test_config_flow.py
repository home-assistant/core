"""Test the Bosch SHC config flow."""
from unittest.mock import PropertyMock

from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCmDNSError,
)
from boschshcpy.information import SHCInformation

from homeassistant import config_entries, setup
from homeassistant.components.bosch_shc.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_SETTINGS = {
    "name": "Test name",
    "device": {"mac": "test-mac", "hostname": "test-host"},
}
DISCOVERY_INFO = {
    "host": "1.1.1.1",
    "port": 0,
    "hostname": "shc012345.local.",
    "type": "_http._tcp.local.",
    "name": "Bosch SHC [test-mac]._http._tcp.local.",
}


async def test_form_user(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.mac_address",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {}

    with patch("boschshcpy.session.SHCSession.authenticate",), patch(
        "homeassistant.components.bosch_shc.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bosch_shc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"ssl_certificate": "test-cert.pem", "ssl_key": "test-key.pem"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "shc012345"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": "test-cert.pem",
        "ssl_key": "test-key.pem",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_get_info_connection_error(hass):
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
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_get_info_mdns_error(hass):
    """Test we handle a mdns error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        side_effect=SHCmDNSError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_get_info_exception(hass):
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
    assert result2["errors"] == {"base": "unknown"}


async def test_form_user_invalid_auth(hass):
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
        "boschshcpy.information.SHCInformation.mac_address",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession",
        side_effect=SHCAuthenticationError,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"ssl_certificate": "test-cert.pem", "ssl_key": "test-key.pem"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_form_validate_connection_error(hass):
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
        "boschshcpy.information.SHCInformation.mac_address",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=SHCConnectionError,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"ssl_certificate": "test-cert.pem", "ssl_key": "test-key.pem"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_validate_mdns_error(hass):
    """Test we handle mDNS error."""
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
        "boschshcpy.information.SHCInformation.mac_address",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=SHCmDNSError,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"ssl_certificate": "test-cert.pem", "ssl_key": "test-key.pem"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_validate_exception(hass):
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
        "boschshcpy.information.SHCInformation.mac_address",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession.authenticate",
        side_effect=Exception,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"ssl_certificate": "test-cert.pem", "ssl_key": "test-key.pem"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
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
        "boschshcpy.information.SHCInformation.mac_address",
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


async def test_zeroconf(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "boschshcpy.session.SHCSession.mdns_info",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.name",
        new_callable=PropertyMock,
        return_value="shc012345",
    ), patch(
        "boschshcpy.information.SHCInformation.mac_address",
        new_callable=PropertyMock,
        return_value="test-mac",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "form"
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shc012345.local."

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    with patch("boschshcpy.session.SHCSession.authenticate",), patch(
        "homeassistant.components.bosch_shc.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bosch_shc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"ssl_certificate": "test-cert.pem", "ssl_key": "test-key.pem"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "shc012345"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": "test-cert.pem",
        "ssl_key": "test-key.pem",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_already_configured(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
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
        "boschshcpy.information.SHCInformation.mac_address",
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


async def test_zeroconf_cannot_connect(hass):
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


async def test_zeroconf_mdns_error(hass):
    """Test for mDNS error in discovery step."""
    with patch("boschshcpy.session.SHCSession.mdns_info", side_effect=SHCmDNSError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_not_bosch_shc(hass):
    """Test we filter out non-bosch_shc devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={"host": "1.1.1.1", "name": "notboschshc"},
        context={"source": config_entries.SOURCE_ZEROCONF},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_bosch_shc"
