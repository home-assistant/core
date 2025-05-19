"""Teste da plataforma switch Redgtech."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.redgtech.switch import RedgtechSwitch
from homeassistant.components.redgtech.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_ON, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from redgtech_api.api import RedgtechConnectionError
from tests.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers import device_registry as dr


@pytest.fixture
def mock_device():
    """Cria um dispositivo simulado."""
    device = MagicMock()
    device.id = "1234-5678"
    device.name = "Teste Interruptor"
    device.state = STATE_OFF
    return device


@pytest.fixture
def mock_coordinator(mock_device):
    """Cria um coordenador simulado."""
    coordinator = AsyncMock()
    coordinator.data = [mock_device]
    coordinator.api = AsyncMock()
    coordinator.api.set_switch_state = AsyncMock()
    coordinator.access_token = "token_teste"
    coordinator.email = "teste@exemplo.com"
    coordinator.password = "senha123"
    return coordinator


@pytest.fixture
def config_entry(mock_coordinator):
    """Cria uma entrada de configuração simulada."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "teste@exemplo.com", CONF_PASSWORD: "senha123"},
        entry_id="teste_entry",
    )
    entry.runtime_data = mock_coordinator
    return entry


@pytest.fixture
async def setup_switch(hass: HomeAssistant, config_entry, mock_coordinator, mock_device):
    """Configura a plataforma switch para testes usando patch de plataforma."""

    with patch(
        "homeassistant.components.redgtech.RedgtechDataUpdateCoordinator",
        return_value=mock_coordinator,
    ), patch("homeassistant.components.redgtech.PLATFORMS", [Platform.SWITCH]):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"switch.{mock_device.name.lower().replace(' ', '_')}"
    return entity_id


async def test_initial_state(hass: HomeAssistant, setup_switch):
    """Teste o estado inicial do switch."""
    entity_id = setup_switch
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_turn_on_switch(hass: HomeAssistant, setup_switch, mock_coordinator, mock_device):
    """Teste ligar o switch via serviço turn_on."""
    entity_id = setup_switch

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )

    mock_coordinator.api.set_switch_state.assert_awaited_once_with(
        mock_device.id, True, mock_coordinator.access_token
    )

    mock_device.state = STATE_ON
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_turn_off_switch(hass: HomeAssistant, setup_switch, mock_coordinator, mock_device):
    """Teste desligar o switch via serviço turn_off."""
    entity_id = setup_switch
    mock_device.state = STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )

    mock_coordinator.api.set_switch_state.assert_awaited_once_with(
        mock_device.id, False, mock_coordinator.access_token
    )

    mock_device.state = STATE_OFF
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_handle_connection_error(hass: HomeAssistant, setup_switch, mock_coordinator):
    """Teste erro de conexão ao ligar o switch gera HomeAssistantError."""
    entity_id = setup_switch
    mock_coordinator.api.set_switch_state.side_effect = RedgtechConnectionError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )

    mock_coordinator.api.set_switch_state.assert_awaited_once()
