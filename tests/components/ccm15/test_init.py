"""Tests for the ccm15 component."""

from unittest.mock import AsyncMock, patch

from ccm15 import CCM15DeviceState, CCM15ReturnCode, CCM15SlaveDevice
import pytest

from homeassistant.components.ccm15.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

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


@pytest.mark.usefixtures("ccm15_device")
async def test_coordinator_set_state_wrong_password_raises(
    hass: HomeAssistant,
) -> None:
    """WRONG_PASSWORD from the library surfaces as ConfigEntryAuthFailed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data

    with (
        patch.object(
            coordinator._ccm15,
            "async_set_state",
            AsyncMock(return_value=CCM15ReturnCode.WRONG_PASSWORD),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator.async_set_state(0, coordinator.data.devices[0])


@pytest.mark.usefixtures("ccm15_device")
async def test_coordinator_set_state_ok_requests_refresh(
    hass: HomeAssistant,
) -> None:
    """OK from the library triggers a coordinator refresh."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data

    with (
        patch.object(
            coordinator._ccm15,
            "async_set_state",
            AsyncMock(return_value=CCM15ReturnCode.OK),
        ),
        patch.object(coordinator, "async_request_refresh", AsyncMock()) as mock_refresh,
    ):
        await coordinator.async_set_state(0, coordinator.data.devices[0])

    mock_refresh.assert_awaited_once()


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
