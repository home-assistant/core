"""Tests for the Gree Integration."""

from unittest.mock import AsyncMock, patch

from greeclimate.exceptions import DeviceTimeoutError
import pytest

from homeassistant import config_entries
from homeassistant.components.gree.const import CONF_IP_ADDRESS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import FakeDiscovery, build_device_mock

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


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
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}

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
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
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

    with patch(
        "homeassistant.components.gree.config_flow.Device",
        return_value=mock_device,
    ):
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

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_step_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual step shows error when device cannot be reached."""
    mock_device = build_device_mock()
    mock_device.bind = AsyncMock(side_effect=DeviceTimeoutError)

    with patch(
        "homeassistant.components.gree.config_flow.Device",
        return_value=mock_device,
    ):
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
        assert result["errors"] == {"base": "cannot_connect"}

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 0


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

    with patch(
        "homeassistant.components.gree.config_flow.Device",
        return_value=mock_device,
    ):
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
