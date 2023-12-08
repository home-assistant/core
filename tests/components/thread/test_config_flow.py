"""Test the Thread config flow."""
from ipaddress import ip_address
from unittest.mock import patch

from homeassistant.components import thread, zeroconf
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_ZEROCONF_RECORD = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="HomeAssistant OpenThreadBorderRouter #0BBF",
    name="HomeAssistant OpenThreadBorderRouter #0BBF._meshcop._udp.local.",
    port=8080,
    properties={
        "rv": "1",
        "vn": "HomeAssistant",
        "mn": "OpenThreadBorderRouter",
        "nn": "OpenThread HC",
        "xp": "\xe6\x0f\xc7\xc1\x86!,\xe5",
        "tv": "1.3.0",
        "xa": "\xae\xeb/YKW\x0b\xbf",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
    type="_meshcop._udp.local.",
)


async def test_import(hass: HomeAssistant) -> None:
    """Test the import flow."""
    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "import"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thread"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(thread.DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Thread"
    assert config_entry.unique_id is None


async def test_import_then_zeroconf(hass: HomeAssistant) -> None:
    """Test the import flow."""
    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "import"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "zeroconf"}, data=TEST_ZEROCONF_RECORD
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user(hass: HomeAssistant) -> None:
    """Test the user flow."""
    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "user"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thread"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(thread.DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Thread"
    assert config_entry.unique_id is None


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test the zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        thread.DOMAIN, context={"source": "zeroconf"}, data=TEST_ZEROCONF_RECORD
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thread"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(thread.DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Thread"
    assert config_entry.unique_id is None


async def test_zeroconf_setup_onboarding(hass: HomeAssistant) -> None:
    """Test we automatically finish a zeroconf flow during onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=False
    ), patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "zeroconf"}, data=TEST_ZEROCONF_RECORD
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thread"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_then_import(hass: HomeAssistant) -> None:
    """Test the import flow."""
    result = await hass.config_entries.flow.async_init(
        thread.DOMAIN, context={"source": "zeroconf"}, data=TEST_ZEROCONF_RECORD
    )
    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY

    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "import"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0
