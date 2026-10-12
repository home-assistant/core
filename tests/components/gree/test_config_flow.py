"""Tests for the Gree Integration."""

from unittest.mock import AsyncMock, patch

from greeclimate.exceptions import DeviceTimeoutError
import pytest

from homeassistant import config_entries
from homeassistant.components.gree.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import FakeDiscovery, build_device_mock

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

_PATCH_BIND = "homeassistant.components.gree.config_flow.async_create_and_bind_device"


async def test_user_step_shows_menu(hass: HomeAssistant) -> None:
    """Test that the user step shows a menu with scan and manual options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["scan", "manual"]


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_scan_finds_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test scan step creates entry when devices are found."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}
        assert result["result"].unique_id == DOMAIN

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_scan_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test scan step aborts when no devices are found."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ) as discovery:
        discovery.return_value.mock_devices = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 0


async def test_manual_step_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual step creates entry on successful connection."""
    mock_device = build_device_mock(
        name="test-device", ipAddress="192.168.1.100", mac="aabbcc112233"
    )

    with patch(_PATCH_BIND, return_value=mock_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "test-device"
        assert result["data"] == {CONF_IP_ADDRESS: "192.168.1.100"}
        assert result["result"].unique_id == "aabbcc112233"

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (DeviceTimeoutError(), "cannot_connect"),
        (OSError("Network unreachable"), "cannot_connect"),
        (Exception("unexpected"), "unknown"),
    ],
)
async def test_manual_step_bind_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test manual step shows an error when binding fails and can recover."""
    mock_device = build_device_mock(
        name="test-device", ipAddress="192.168.1.100", mac="aabbcc112233"
    )

    with patch(_PATCH_BIND, side_effect=side_effect) as mock_bind:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}
        assert len(mock_setup_entry.mock_calls) == 0

        mock_bind.side_effect = None
        mock_bind.return_value = mock_device

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "aabbcc112233"

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_step_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual step aborts when device is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbcc112233",
        data={CONF_IP_ADDRESS: "192.168.1.100"},
    )
    existing_entry.add_to_hass(hass)

    mock_device = build_device_mock(
        name="test-device", ipAddress="192.168.1.200", mac="aabbcc112233"
    )

    with patch(_PATCH_BIND, return_value=mock_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.200"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_scan_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test scan step aborts when a discovery entry already exists."""
    existing_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "scan"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_step_allowed_alongside_discovery_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual step is allowed even when a discovery entry exists."""
    existing_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    existing_entry.add_to_hass(hass)

    mock_device = build_device_mock(
        name="test-device", ipAddress="192.168.1.100", mac="aabbcc112233"
    )

    with patch(_PATCH_BIND, return_value=mock_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "aabbcc112233"

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 2


async def test_manual_step_invalid_ip(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual step shows error for invalid IP address and can recover."""
    mock_device = build_device_mock(
        name="test-device", ipAddress="192.168.1.100", mac="aabbcc112233"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "not-an-ip"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"ip_address": "invalid_host"}

    with patch(_PATCH_BIND, return_value=mock_device):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112233"

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
