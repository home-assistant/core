"""Tests for the solax integration setup."""

from unittest.mock import patch

import pytest
from solax.inverter import InverterError, InverterResponse
from solax.inverters import X1MiniV34

from homeassistant.components.solax.const import DOMAIN, INVERTER_MODELS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def __mock_get_data() -> InverterResponse:
    return InverterResponse(
        data=dict.fromkeys(X1MiniV34.sensor_map(), 0),
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


@pytest.mark.parametrize(
    ("entry_data", "expected_inverters"),
    [
        pytest.param(
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
            None,
            id="auto_detect",
        ),
        pytest.param(
            {
                CONF_IP_ADDRESS: "192.168.1.87",
                CONF_PORT: 80,
                CONF_PASSWORD: "password",
                CONF_MODEL: "x1_mini_v34",
            },
            [INVERTER_MODELS["x1_mini_v34"]],
            id="model_selected",
        ),
    ],
)
async def test_setup_entry_success(
    hass: HomeAssistant,
    entry_data: dict[str, str | int],
    expected_inverters: list[type] | None,
) -> None:
    """Test the entry loads and discover() is called with the right inverters."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id="ABCDEFGHIJ")
    entry.add_to_hass(hass)

    inverter = next(
        iter(
            X1MiniV34.build_all_variants(
                entry_data[CONF_IP_ADDRESS],
                entry_data[CONF_PORT],
                entry_data[CONF_PASSWORD],
            )
        )
    )

    with (
        patch(
            "homeassistant.components.solax.discover", return_value=inverter
        ) as mock_discover,
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert mock_discover.call_args.kwargs.get("inverters") == expected_inverters


async def test_coordinator_update_failure(hass: HomeAssistant) -> None:
    """Test an InverterError during a refresh is converted to UpdateFailed."""
    entry_data = {
        CONF_IP_ADDRESS: "192.168.1.87",
        CONF_PORT: 80,
        CONF_PASSWORD: "password",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id="ABCDEFGHIJ")
    entry.add_to_hass(hass)

    inverter = next(
        iter(
            X1MiniV34.build_all_variants(
                entry_data[CONF_IP_ADDRESS],
                entry_data[CONF_PORT],
                entry_data[CONF_PASSWORD],
            )
        )
    )

    with (
        patch("homeassistant.components.solax.discover", return_value=inverter),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data.coordinator

    with patch("solax.RealTimeAPI.get_data", side_effect=InverterError):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test ConfigEntryNotReady is raised when discovery fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.87",
            CONF_PORT: 80,
            CONF_PASSWORD: "password",
        },
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.solax.discover", side_effect=ConnectionError):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
