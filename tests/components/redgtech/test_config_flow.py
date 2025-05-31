"""Testa o fluxo de configuração do Redgtech."""

import pytest
from unittest.mock import AsyncMock, patch
from tests.common import MockConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, AbortFlow
from homeassistant.components.redgtech.config_flow import RedgtechConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.components.redgtech.const import DOMAIN
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError


TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "123456"
FAKE_TOKEN = "fake_token"


@pytest.fixture
def mock_redgtech_login():
    """Mocka o método login da RedgtechAPI para retornar um token falso."""
    with patch(
        "homeassistant.components.redgtech.config_flow.RedgtechAPI.login",
        return_value=FAKE_TOKEN,
    ) as mock:
        yield mock


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (RedgtechAuthError, "invalid_auth"),
        (RedgtechConnectionError, "cannot_connect"),
        (Exception("Erro genérico"), "unknown"),
    ],
)
async def test_user_step_errors(hass: HomeAssistant, side_effect, expected_error):
    """Testa tratamento de erros no passo do usuário."""
    flow = RedgtechConfigFlow()
    flow.hass = hass

    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    with patch(
        "homeassistant.components.redgtech.config_flow.RedgtechAPI.login",
        side_effect=side_effect,
    ):
        result = await flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_user_step_creates_entry(hass: HomeAssistant, mock_redgtech_login):
    """Testa criação correta de entrada na configuração."""
    flow = RedgtechConfigFlow()
    flow.hass = hass

    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    result = await flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == user_input


async def test_user_step_duplicate_entry(hass: HomeAssistant, mock_redgtech_login):
    """Testa tentativa de adicionar entrada duplicada."""
    # Cria entrada de configuração simulada
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: TEST_EMAIL},
    )
    existing_entry.add_to_hass(hass)

    # Inicia o fluxo
    flow = RedgtechConfigFlow()
    flow.hass = hass

    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    # Captura a exceção AbortFlow
    with pytest.raises(AbortFlow) as exc_info:
        await flow.async_step_user(user_input)

    # ✅ Acessa o motivo corretamente
    assert exc_info.value.reason == "already_configured"
