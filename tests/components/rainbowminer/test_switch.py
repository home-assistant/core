"""Test the RainbowMiner mining switch."""

from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import (
    VALID_ACTIVE_MINERS,
    VALID_BALANCES,
    VALID_CURRENT_PROFIT,
    VALID_STATUS,
    VALID_UPTIME,
    VALID_VERSION,
    mock_rainbowminer_endpoints,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

SWITCH_ENTITY_ID = "switch.rainbowminer_mining"


def _register_all(aioclient_mock: AiohttpClientMocker, *, paused: bool = False) -> None:
    """Register canned responses for all endpoints."""
    mock_rainbowminer_endpoints(
        aioclient_mock,
        status={**VALID_STATUS, "Pause": paused},
        current_profit=VALID_CURRENT_PROFIT,
        uptime=VALID_UPTIME,
        active_miners=VALID_ACTIVE_MINERS,
        version=VALID_VERSION,
        balances=VALID_BALANCES,
        pause=True,
        resume=False,
    )


async def _setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Set up the integration."""
    _register_all(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 4000},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_switch_is_on_when_mining(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the switch is on when mining is running."""
    await _setup(hass, aioclient_mock)

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_is_off_when_paused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the switch is off when mining is paused."""
    _register_all(aioclient_mock, paused=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 4000},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_turn_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turning the switch off pauses mining."""
    await _setup(hass, aioclient_mock)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    pause_requests = [
        call for call in aioclient_mock.mock_calls if "pause?action=set" in str(call[1])
    ]
    assert pause_requests


async def test_switch_turn_on(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turning the switch on resumes mining."""
    _register_all(aioclient_mock, paused=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 4000},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    resume_requests = [
        call
        for call in aioclient_mock.mock_calls
        if "pause?action=reset" in str(call[1])
    ]
    assert resume_requests
