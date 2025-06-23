"""Test the Livisi Home Assistant config flow."""

from unittest.mock import patch

from livisi import errors as livisi_errors
import pytest

from homeassistant.components.livisi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    VALID_CONFIG,
    mocked_livisi_controller,
    mocked_livisi_login,
    mocked_livisi_setup_entry,
)


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test create LIVISI entity."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with mocked_livisi_login(), mocked_livisi_controller(), mocked_livisi_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "SHC Classic"
        assert result["data"]["host"] == "1.1.1.1"
        assert result["data"]["password"] == "test"


@pytest.mark.parametrize(
    ("exception", "expected_reason"),
    [
        (livisi_errors.ShcUnreachableException(), "cannot_connect"),
        (livisi_errors.IncorrectIpAddressException(), "wrong_ip_address"),
        (livisi_errors.WrongCredentialException(), "wrong_password"),
    ],
)
async def test_create_entity_after_login_error(
    hass: HomeAssistant, exception: livisi_errors.LivisiException, expected_reason: str
) -> None:
    """Test the LIVISI integration can create an entity after the user had login errors."""
    with patch(
        "homeassistant.components.livisi.config_flow.AioLivisi.async_set_token",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_CONFIG
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == expected_reason
    with mocked_livisi_login(), mocked_livisi_controller(), mocked_livisi_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_CONFIG,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
