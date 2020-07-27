"""Test the Volumio config flow."""
from homeassistant import config_entries
from homeassistant.components.volumio.config_flow import CannotConnectError
from homeassistant.components.volumio.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry

TEST_SYSTEM_INFO = {"id": "1111-1111-1111-1111", "name": "TestVolumio"}


TEST_CONNECTION = {
    "host": "1.1.1.1",
    "port": 3000,
}


TEST_DISCOVERY = {
    "host": "1.1.1.1",
    "port": 3000,
    "properties": {"volumioName": "discovered", "UUID": "2222-2222-2222-2222"},
}

TEST_DISCOVERY_RESULT = {
    "host": TEST_DISCOVERY["host"],
    "port": TEST_DISCOVERY["port"],
    "id": TEST_DISCOVERY["properties"]["UUID"],
    "name": TEST_DISCOVERY["properties"]["volumioName"],
}


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        return_value=TEST_SYSTEM_INFO,
    ), patch(
        "homeassistant.components.volumio.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.volumio.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONNECTION,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "TestVolumio"
    assert result2["data"] == {**TEST_SYSTEM_INFO, **TEST_CONNECTION}

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_updates_unique_id(hass):
    """Test a duplicate id aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SYSTEM_INFO["id"],
        data={
            "host": "dummy",
            "port": 11,
            "name": "dummy",
            "id": TEST_SYSTEM_INFO["id"],
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        return_value=TEST_SYSTEM_INFO,
    ), patch("homeassistant.components.volumio.async_setup", return_value=True), patch(
        "homeassistant.components.volumio.async_setup_entry", return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONNECTION,
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"

    assert entry.data == {**TEST_SYSTEM_INFO, **TEST_CONNECTION}


async def test_empty_system_info(hass):
    """Test old volumio versions with empty system info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        return_value={},
    ), patch(
        "homeassistant.components.volumio.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.volumio.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONNECTION,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_CONNECTION["host"]
    assert result2["data"] == {
        "host": TEST_CONNECTION["host"],
        "port": TEST_CONNECTION["port"],
        "name": TEST_CONNECTION["host"],
        "id": None,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        side_effect=CannotConnectError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONNECTION,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass):
    """Test we handle generic error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONNECTION,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_discovery(hass):
    """Test discovery flow works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        return_value=TEST_SYSTEM_INFO,
    ), patch(
        "homeassistant.components.volumio.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.volumio.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_DISCOVERY_RESULT["name"]
    assert result2["data"] == TEST_DISCOVERY_RESULT

    assert result2["result"]
    assert result2["result"].unique_id == TEST_DISCOVERY_RESULT["id"]

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_cannot_connect(hass):
    """Test discovery aborts if cannot connect."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        side_effect=CannotConnectError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "cannot_connect"


async def test_discovery_duplicate_data(hass):
    """Test discovery aborts if same mDNS packet arrives."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_discovery_updates_unique_id(hass):
    """Test a duplicate discovery id aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DISCOVERY_RESULT["id"],
        data={
            "host": "dummy",
            "port": 11,
            "name": "dummy",
            "id": TEST_DISCOVERY_RESULT["id"],
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    assert entry.data == TEST_DISCOVERY_RESULT
