"""Test the Switcher config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.switcher_kis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .consts import DUMMY_PLUG_DEVICE, DUMMY_WATER_HEATER_DEVICE

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "mock_bridge",
    [
        [
            DUMMY_PLUG_DEVICE,
            DUMMY_WATER_HEATER_DEVICE,
            # Make sure we don't detect the same device twice
            DUMMY_WATER_HEATER_DEVICE,
        ]
    ],
    indirect=True,
)
async def test_user_setup(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_bridge
) -> None:
    """Test we can finish a config flow."""
    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert mock_bridge.is_running is False
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Switcher"
        assert result2["result"].data == {}

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_abort_no_devices_found(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_bridge
) -> None:
    """Test we abort a config flow if no devices found."""
    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert mock_bridge.is_running is False
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "no_devices_found"

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
