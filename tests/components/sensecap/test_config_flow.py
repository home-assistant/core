"""Test user setup and LoRaWAN discovery."""

from unittest.mock import patch

import pytest

from homeassistant.components.lorawan import LoRaWANDiscoveryInfo
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize(
    ("source", "data"),
    [(SOURCE_USER, None), (SOURCE_INTEGRATION_DISCOVERY, LoRaWANDiscoveryInfo())],
)
async def test_setup(
    hass: HomeAssistant, source: str, data: LoRaWANDiscoveryInfo | None
) -> None:
    """Both entry points ask for confirmation and store no connection selection."""
    result = await hass.config_entries.flow.async_init(
        "sensecap", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    with patch(
        "homeassistant.components.sensecap.async_setup_entry", return_value=True
    ) as setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SenseCAP"
    assert result["data"] == {}
    assert result["result"].unique_id == "sensecap"
    setup.assert_called_once()


@pytest.mark.parametrize(
    ("source", "data"),
    [(SOURCE_USER, None), (SOURCE_INTEGRATION_DISCOVERY, LoRaWANDiscoveryInfo())],
)
@pytest.mark.usefixtures("config_entry")
async def test_already_configured(
    hass: HomeAssistant, source: str, data: LoRaWANDiscoveryInfo | None
) -> None:
    """Only one SenseCAP entry is needed for all connections."""
    result = await hass.config_entries.flow.async_init(
        "sensecap", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_duplicate_discovery(hass: HomeAssistant) -> None:
    """Concurrent discoveries share one confirmation flow."""
    await hass.config_entries.flow.async_init(
        "sensecap",
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=LoRaWANDiscoveryInfo(),
    )
    result = await hass.config_entries.flow.async_init(
        "sensecap",
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=LoRaWANDiscoveryInfo(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
