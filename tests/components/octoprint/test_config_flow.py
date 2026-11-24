"""Test the OctoPrint config flow."""

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import patch

from pyoctoprintapi import ApiError, DiscoverySettings
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.octoprint.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_server_info",
            return_value=True,
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch(
            "homeassistant.components.octoprint.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
    assert result2["result"].unique_id == "uuid"
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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.SHOW_PROGRESS

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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch("homeassistant.components.octoprint.async_setup", return_value=True),
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ),
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
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.SHOW_PROGRESS

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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch("homeassistant.components.octoprint.async_setup", return_value=True),
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ),
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
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_show_zerconf_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=80,
            properties={"uuid": "83747482", "path": "/foo/"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
        },
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_server_info",
            return_value=True,
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch("homeassistant.components.octoprint.async_setup", return_value=True),
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ),
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "uuid"


async def test_show_ssdp_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            upnp={
                "presentationURL": "http://192.168.1.123:80/discovery/device.xml",
                "port": 80,
                "UDN": "uuid:83747482",
            },
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "testuser",
        },
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_server_info",
            return_value=True,
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch("homeassistant.components.octoprint.async_setup", return_value=True),
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ),
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "uuid"


async def test_import_yaml(hass: HomeAssistant) -> None:
    """Test that the yaml import works."""
    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_server_info",
            return_value=True,
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
        ),
        patch("homeassistant.components.octoprint.async_setup", return_value=True),
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ),
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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "uuid"
    assert "errors" not in result


async def test_import_duplicate_yaml(hass: HomeAssistant) -> None:
    """Test that the yaml import works."""
    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.123"},
        source=config_entries.SOURCE_IMPORT,
        unique_id="uuid",
    ).add_to_hass(hass)

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
        ) as request_app_key,
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
        assert len(request_app_key.mock_calls) == 0

    assert result["type"] is FlowResultType.ABORT
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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch("pyoctoprintapi.OctoprintClient.request_app_key", side_effect=ApiError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch("pyoctoprintapi.OctoprintClient.request_app_key", side_effect=Exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
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
    assert result["type"] is FlowResultType.FORM
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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with (
        patch(
            "pyoctoprintapi.OctoprintClient.get_server_info",
            return_value=True,
        ),
        patch(
            "pyoctoprintapi.OctoprintClient.get_discovery_info",
            return_value=DiscoverySettings({"upnpUuid": "uuid"}),
        ),
        patch(
            "homeassistant.components.octoprint.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.octoprint.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
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
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=80,
            properties={"uuid": "83747482", "path": "/foo/"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
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
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            upnp={
                "presentationURL": "http://192.168.1.123:80/discovery/device.xml",
                "port": 80,
                "UDN": "uuid:83747482",
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT
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
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
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
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    with patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


RECONFIGURE_INPUT = {
    "host": "2.2.2.2",
    "port": 443,
    "path": "/octoprint",
    "ssl": True,
    "verify_ssl": False,
}


@pytest.fixture
def mock_reconfigure_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry to reconfigure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "testuser",
            "host": "1.1.1.1",
            "port": 81,
            "ssl": False,
            "verify_ssl": True,
            "path": "/",
            "api_key": "test-key",
        },
        unique_id="uuid",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.octoprint.async_setup_entry", return_value=None
    ):
        yield


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant, mock_reconfigure_entry: MockConfigEntry
) -> None:
    """Test reconfiguring the connection settings."""
    result = await mock_reconfigure_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_reconfigure_entry.data == {
        "username": "testuser",
        "host": "2.2.2.2",
        "port": 443,
        "ssl": True,
        "verify_ssl": False,
        "path": "/octoprint",
        "api_key": "test-key",
    }


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(ApiError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_reconfigure_entry: MockConfigEntry,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test errors during reconfigure and recovery."""
    result = await mock_reconfigure_entry.start_reconfigure_flow(hass)

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_reconfigure_entry.data["host"] == "2.2.2.2"


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant, mock_reconfigure_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when the address points to another instance."""
    result = await mock_reconfigure_entry.start_reconfigure_flow(hass)

    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "other-uuid"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_reconfigure_entry.data["host"] == "1.1.1.1"
