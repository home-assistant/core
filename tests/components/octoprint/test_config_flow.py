"""Test the OctoPrint config flow."""
from unittest.mock import patch

from pyoctoprintapi import (
    ApiError,
    DiscoverySettings,
    OctoprintJobInfo,
    OctoprintPrinterInfo,
)

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.octoprint.config_flow import CannotConnect
from homeassistant.components.octoprint.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

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
    ) as mock_setup, patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
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
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        side_effect=CannotConnect,
    ), patch("pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "testuser",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle a random error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        side_effect=Exception,
    ), patch("pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "testuser",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_show_zerconf_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "host": "192.168.1.123",
            "port": 80,
            "hostname": "example.local.",
            "uuid": "83747482",
            "properties": {"uuid": "83747482", "path": "/foo/"},
        },
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {"printing": True, "error": False},
                    "text": "Operational",
                },
                "temperature": [],
            }
        ),
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_job_info",
        return_value=OctoprintJobInfo(
            {
                "job": {},
                "progress": {"completion": 50},
            }
        ),
    ), patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "testuser"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_show_ssdp_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "presentationURL": "http://192.168.1.123:80/discovery/device.xml",
            "port": 80,
            "UDN": "uuid:83747482",
        },
    )
    assert result["type"] == "form"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {"printing": True, "error": False},
                    "text": "Operational",
                },
                "temperature": [],
            }
        ),
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_job_info",
        return_value=OctoprintJobInfo(
            {
                "job": {},
                "progress": {"completion": 50},
            }
        ),
    ), patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "testuser"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


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
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
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
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ), patch(
        "pyoctoprintapi.OctoprintClient.request_app_key", return_value="test-key"
    ) as request_app_key, patch(
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
        assert len(request_app_key.mock_calls) == 0

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_failed_auth(hass: HomeAssistant) -> None:
    """Test we handle a random error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyoctoprintapi.OctoprintClient.request_app_key",
        side_effect=ApiError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "testuser",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
