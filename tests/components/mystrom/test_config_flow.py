"""Test the myStrom config flow."""

from unittest.mock import AsyncMock, patch

from pymystrom.exceptions import MyStromConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import DEVICE_MAC

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

DHCP_SERVICE_INFO = DhcpServiceInfo(
    ip="1.2.3.4",
    hostname="mystrom-switch-946498",
    macaddress="083a8d946498",
)


async def test_form_combined(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 101, "mac": DEVICE_MAC}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "myStrom Device"
    assert result2["data"] == {"host": "1.1.1.1"}


async def test_form_duplicates(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test abort on duplicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "pymystrom.get_device_info",
        return_value={"type": 101, "mac": DEVICE_MAC},
    ) as mock_session:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    mock_session.assert_called_once()


async def test_wong_answer_from_device(hass: HomeAssistant) -> None:
    """Test handling of wrong answers from the device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "pymystrom.get_device_info",
        side_effect=MyStromConnectionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "pymystrom.get_device_info",
        return_value={"type": 101, "mac": DEVICE_MAC},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "myStrom Device"
    assert result2["data"] == {"host": "1.1.1.1"}


async def test_dhcp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test DHCP discovery shows a confirmation form and creates an entry."""
    with patch(
        "homeassistant.components.mystrom.config_flow.pymystrom.get_device_info",
        return_value={"type": 101, "mac": DEVICE_MAC},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DHCP_SERVICE_INFO,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "myStrom Device"
    assert result["data"] == {"host": DHCP_SERVICE_INFO.ip}
    assert result["result"].unique_id == "083A8D946498"


async def test_dhcp_discovery_cannot_connect(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when the device is unreachable."""
    with patch(
        "homeassistant.components.mystrom.config_flow.pymystrom.get_device_info",
        side_effect=MyStromConnectionError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DHCP_SERVICE_INFO,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_dhcp_discovery_already_configured_updates_host(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test DHCP discovery updates the host of an already-configured entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="083A8D946498",
        data={CONF_HOST: "1.1.1.1"},
        title="myStrom Device",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == DHCP_SERVICE_INFO.ip
