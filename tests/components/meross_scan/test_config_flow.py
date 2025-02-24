"""Tests for the meross_scan Integration."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.meross_scan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_DEVICE, mock_discovery

from tests.common import MockConfigEntry


async def test_found_device(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.meross_scan.config_flow.Discovery",
        return_value=mock_discovery(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.1"},
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "em06"
        assert result2["data"] == {
            "host": "192.168.1.1",
            "device": MOCK_DEVICE,
        }


async def test_no_device(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.meross_scan.config_flow.Discovery",
        return_value=mock_discovery(),
    ) as discovery:
        discovery.return_value.broadcast_msg = AsyncMock(return_value=None)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.1"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "no_devices_found"}


async def test_reconfigure_successful(
    hass: HomeAssistant,
) -> None:
    """Test starting a reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-mac",
        data={"host": "192.168.1.1", "device": MOCK_DEVICE},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.meross_scan.config_flow.Discovery",
        return_value=mock_discovery(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.2"},
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"
        assert entry.data == {"host": "192.168.1.2", "device": MOCK_DEVICE}


async def test_reconfigure_unsuccessful(
    hass: HomeAssistant,
) -> None:
    """Test reconfiguration flow failed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-mac",
        data={"host": "192.168.1.1", "device": MOCK_DEVICE},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.meross_scan.config_flow.Discovery",
        return_value=mock_discovery(),
    ) as discovery:
        MOCK_DEVICE["mac"] = "test-another-mac"
        discovery.return_value.broadcast_msg = AsyncMock(return_value=MOCK_DEVICE)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.2"},
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "another_device"
