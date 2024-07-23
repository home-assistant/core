"""Test the Volumio config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.volumio.config_flow import CannotConnectError
from homeassistant.components.volumio.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_SYSTEM_INFO = {"id": "1111-1111-1111-1111", "name": "TestVolumio"}


TEST_CONNECTION = {
    "host": "1.1.1.1",
    "port": 3000,
}


TEST_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="mock_hostname",
    name="mock_name",
    port=3000,
    properties={"volumioName": "discovered", "UUID": "2222-2222-2222-2222"},
    type="mock_type",
)

TEST_DISCOVERY_RESULT = {
    "host": TEST_DISCOVERY.host,
    "port": TEST_DISCOVERY.port,
    "id": TEST_DISCOVERY.properties["UUID"],
    "name": TEST_DISCOVERY.properties["volumioName"],
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
            return_value=TEST_SYSTEM_INFO,
        ),
        patch(
            "homeassistant.components.volumio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TestVolumio"
    assert result2["data"] == {**TEST_SYSTEM_INFO, **TEST_CONNECTION}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_updates_unique_id(hass: HomeAssistant) -> None:
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
    with (
        patch(
            "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
            return_value=TEST_SYSTEM_INFO,
        ),
        patch(
            "homeassistant.components.volumio.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    assert entry.data == {**TEST_SYSTEM_INFO, **TEST_CONNECTION}


async def test_empty_system_info(hass: HomeAssistant) -> None:
    """Test old volumio versions with empty system info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
            return_value={},
        ),
        patch(
            "homeassistant.components.volumio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_CONNECTION["host"]
    assert result2["data"] == {
        "host": TEST_CONNECTION["host"],
        "port": TEST_CONNECTION["port"],
        "name": TEST_CONNECTION["host"],
        "id": None,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        side_effect=CannotConnectError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle generic error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_discovery(hass: HomeAssistant) -> None:
    """Test discovery flow works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )

    with (
        patch(
            "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
            return_value=TEST_SYSTEM_INFO,
        ),
        patch(
            "homeassistant.components.volumio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DISCOVERY_RESULT["name"]
    assert result2["data"] == TEST_DISCOVERY_RESULT

    assert result2["result"]
    assert result2["result"].unique_id == TEST_DISCOVERY_RESULT["id"]

    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_cannot_connect(hass: HomeAssistant) -> None:
    """Test discovery aborts if cannot connect."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )

    with patch(
        "homeassistant.components.volumio.config_flow.Volumio.get_system_info",
        side_effect=CannotConnectError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_discovery_duplicate_data(hass: HomeAssistant) -> None:
    """Test discovery aborts if same mDNS packet arrives."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_discovery_updates_unique_id(hass: HomeAssistant) -> None:
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
        state=config_entries.ConfigEntryState.SETUP_RETRY,
    )

    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.volumio.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data == TEST_DISCOVERY_RESULT
    assert len(mock_setup_entry.mock_calls) == 1
