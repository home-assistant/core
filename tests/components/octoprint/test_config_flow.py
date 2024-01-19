"""Test the OctoPrint config flow."""
from ipaddress import ip_address
from unittest.mock import patch

from pyoctoprintapi import ApiError, DiscoverySettings

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp, zeroconf
from homeassistant.components.octoprint.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
                "host": "1.1.1.1",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "username": "testuser",
        "host": "1.1.1.1",
        "api_key": "test-key",
        "name": "Printer",
        "port": 81,
        "ssl": True,
        "path": "/",
        "verify_ssl": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
            "host": "1.1.1.1",
            "name": "Printer",
            "port": 81,
            "ssl": True,
            "path": "/",
        },
    )
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        side_effect=ApiError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
                "host": "1.1.1.1",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "verify_ssl": True,
                "path": "/",
                "api_key": "test-key",
            },
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle a random error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
            "host": "1.1.1.1",
            "name": "Printer",
            "port": 81,
            "ssl": True,
            "path": "/",
        },
    )
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
                "host": "1.1.1.1",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
                "api_key": "test-key",
                "verify_ssl": True,
            },
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


async def test_show_zerconf_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=80,
            properties={"uuid": "83747482", "path": "/foo/"},
            type="mock_type",
        ),
    )
    assert result["type"] == "form"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
        },
    )
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ), patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
                "host": "1.1.1.1",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
                "api_key": "test-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_show_ssdp_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            upnp={
                "presentationURL": "http://192.168.1.123:80/discovery/device.xml",
                "port": 80,
                "UDN": "uuid:83747482",
            },
        ),
    )
    assert result["type"] == "form"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
        },
    )
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ), patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
                "host": "1.1.1.1",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
                "api_key": "test-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_import_yaml(hass: HomeAssistant) -> None:
    """Test that the yaml import works."""
    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ), patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "api_key": "test-key",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert "errors" not in result


async def test_import_duplicate_yaml(hass: HomeAssistant) -> None:
    """Test that the yaml import works."""
    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.123"},
        source=config_entries.SOURCE_IMPORT,
        unique_id="uuid",
    ).add_to_hass(hass)

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ) as request_app_key:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "api_key": "test-key",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()
        assert len(request_app_key.mock_calls) == 0

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_failed_auth(hass: HomeAssistant) -> None:
    """Test we handle a random error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
            "host": "1.1.1.1",
            "name": "Printer",
            "port": 81,
            "ssl": True,
            "path": "/",
        },
    )
    assert result["type"] == "progress"

    with patch("pyoctoprintapi.OctoprintClient.request_app_key", side_effect=ApiError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] == "progress"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == "auth_failed"


async def test_failed_auth_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle a random error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
            "host": "1.1.1.1",
            "name": "Printer",
            "port": 81,
            "ssl": True,
            "path": "/",
        },
    )
    assert result["type"] == "progress"

    with patch("pyoctoprintapi.OctoprintClient.request_app_key", side_effect=Exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] == "progress"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == "auth_failed"


async def test_user_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that duplicate entries abort."""
    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.123"},
        source=config_entries.SOURCE_IMPORT,
        unique_id="uuid",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
                "host": "1.1.1.1",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == "progress"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_duplicate_zerconf_ignored(hass: HomeAssistant) -> None:
    """Test that the duplicate zeroconf isn't shown."""
    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.123"},
        source=config_entries.SOURCE_IMPORT,
        unique_id="83747482",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=80,
            properties={"uuid": "83747482", "path": "/foo/"},
            type="mock_type",
        ),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_duplicate_ssdp_ignored(hass: HomeAssistant) -> None:
    """Test that duplicate ssdp form is note shown."""
    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.123"},
        source=config_entries.SOURCE_IMPORT,
        unique_id="83747482",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            upnp={
                "presentationURL": "http://192.168.1.123:80/discovery/device.xml",
                "port": 80,
                "UDN": "uuid:83747482",
            },
        ),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_reauth_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "testuser",
            "host": "1.1.1.1",
            "name": "Printer",
            "port": 81,
            "ssl": True,
            "path": "/",
        },
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "entry_id": entry.entry_id,
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "testuser",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == "progress"

    with patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"
