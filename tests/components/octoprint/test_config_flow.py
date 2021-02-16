"""Test the OctoPrint config flow."""
from unittest.mock import patch

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
        "homeassistant.components.octoprint.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Printer"
    assert result2["data"] == {
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
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
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
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
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
            "properties": {"uuid": "83747482", "path": "/foo/"},
        },
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result2["step_id"] == "user"
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM

    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_import_yaml(hass: HomeAssistant) -> None:
    """Test that the yaml import works."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "pyoctoprintapi.OctoprintClient.get_server_info",
        return_value=True,
    ), patch(
        "homeassistant.components.octoprint.async_setup", return_value=True
    ), patch(
        "homeassistant.components.octoprint.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_duplicate_import_yaml(hass: HomeAssistant) -> None:
    """Test that the yaml aborts on a reimport."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.123"},
        source=config_entries.SOURCE_IMPORT,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "192.168.1.123",
            "port": 80,
            "name": "Octoprint",
            "path": "/",
            "api_key": "123dfuchxxkks",
            "ssl": False,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
