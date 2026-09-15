"""Tests for the ccm15 component."""

from unittest.mock import patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
import pytest

from homeassistant.components.ccm15.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("ccm15_device")
async def test_load_unload(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_non_contiguous_slots(hass: HomeAssistant) -> None:
    """Entities for sparse slot indices, including >= 32, are available.

    ``devices`` is keyed by the true slot index, which can be sparse and reach
    >= 32. The coordinator must look devices up by key, not assume a contiguous
    0..N-1 range, or any entity past a gap stays permanently unavailable.
    """
    device_state = CCM15DeviceState(
        devices={
            4: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
            33: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
        }
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    for entity_id in ("climate.midea_4", "climate.midea_33"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"


@pytest.mark.usefixtures("network_error_ccm15_device")
async def test_setup_retry_on_connection_error(hass: HomeAssistant) -> None:
    """Setup is retried when the controller cannot be reached."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
