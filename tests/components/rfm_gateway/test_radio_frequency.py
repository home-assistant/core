"""Tests for the RFM Gateway radio frequency platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from rf_protocols import ModulationType

from homeassistant.components import radio_frequency, rfm_gateway
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyCommand

TEST_HOST = "192.0.2.10"
RF_DOMAIN = radio_frequency.DOMAIN


def _mock_caps(
    *,
    supported_modulations: list[str] | None = None,
) -> rfm_gateway.RfmCapabilities:
    """Return mocked gateway capabilities."""
    return rfm_gateway.RfmCapabilities(
        supported_frequency_ranges=[(433_050_000, 434_790_000)],
        supported_modulations=supported_modulations or ["ook"],
        device_name="RFM Gateway",
    )


def _mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the RFM Gateway integration."""
    return MockConfigEntry(
        domain=rfm_gateway.DOMAIN,
        title="RFM Gateway",
        data={rfm_gateway.CONF_HOST: TEST_HOST},
        unique_id=TEST_HOST,
    )


def _entity_id(hass: HomeAssistant) -> str:
    """Return the only RFM Gateway radio frequency entity id."""
    entity_ids = list(hass.states.async_entity_ids(RF_DOMAIN))
    assert len(entity_ids) == 1
    return entity_ids[0]


async def _setup_entry(
    hass: HomeAssistant,
    *,
    capabilities: rfm_gateway.RfmCapabilities | Exception,
) -> MockConfigEntry:
    """Set up the config entry with patched capabilities lookup."""
    assert await async_setup_component(hass, RF_DOMAIN, {})
    await hass.async_block_till_done()

    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    side_effect = capabilities if isinstance(capabilities, Exception) else None
    return_value = None if isinstance(capabilities, Exception) else capabilities

    with patch(
        "homeassistant.components.rfm_gateway.radio_frequency.RfmGatewayClient.async_get_capabilities",
        new=AsyncMock(side_effect=side_effect, return_value=return_value),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_setup_entry_creates_entity(hass: HomeAssistant) -> None:
    """Test setting up the config entry creates the RF entity."""
    entry = await _setup_entry(hass, capabilities=_mock_caps())

    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(_entity_id(hass))
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_setup_entry_failure_sets_setup_error(hass: HomeAssistant) -> None:
    """Test capability fetch failure leaves the entry in setup error."""
    entry = await _setup_entry(
        hass,
        capabilities=rfm_gateway.RfmGatewayConnectionError("cannot_connect"),
    )

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_send_command_success_forwards_payload(hass: HomeAssistant) -> None:
    """Test sending a command forwards the expected raw RF payload."""
    entry = await _setup_entry(hass, capabilities=_mock_caps())
    assert entry.state is ConfigEntryState.LOADED

    entity_id = _entity_id(hass)
    command = MockRadioFrequencyCommand(
        frequency=433_920_000,
        repeat_count=2,
    )

    with patch(
        "homeassistant.components.rfm_gateway.client.RfmGatewayClient.async_send_raw",
        new=AsyncMock(),
    ) as mock_send_raw:
        await radio_frequency.async_send_command(hass, entity_id, command)

    mock_send_raw.assert_awaited_once_with(
        frequency_hz=433_920_000,
        modulation="ook",
        repeat_count=2,
        timings_us=[350, -1050, 350, -350],
    )


async def test_send_command_rejects_unsupported_modulation(hass: HomeAssistant) -> None:
    """Test unsupported modulation is rejected before sending to the gateway."""
    entry = await _setup_entry(hass, capabilities=_mock_caps())
    assert entry.state is ConfigEntryState.LOADED

    entity_id = _entity_id(hass)
    command = MockRadioFrequencyCommand(
        frequency=433_920_000,
        modulation="unsupported",  # type: ignore[arg-type]
    )

    with pytest.raises(HomeAssistantError, match="Gateway does not support modulation"):
        await radio_frequency.async_send_command(hass, entity_id, command)


async def test_send_command_failure_marks_entity_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test transmit failure marks the entity unavailable."""
    entry = await _setup_entry(hass, capabilities=_mock_caps())
    assert entry.state is ConfigEntryState.LOADED

    entity_id = _entity_id(hass)
    command = MockRadioFrequencyCommand(
        frequency=433_920_000,
        modulation=ModulationType.OOK,
    )

    with (
        patch(
            "homeassistant.components.rfm_gateway.client.RfmGatewayClient.async_send_raw",
            new=AsyncMock(
                side_effect=rfm_gateway.RfmGatewayProtocolError("parameter error")
            ),
        ),
        pytest.raises(HomeAssistantError, match="RF transmit via 192.0.2.10 failed"),
    ):
        await radio_frequency.async_send_command(hass, entity_id, command)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
