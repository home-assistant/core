"""Test the Livisi Home Assistant config flow."""
from unittest.mock import patch

from aiolivisi import errors as livisi_errors
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.livisi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import (
    VALID_CONFIG,
    create_entry,
    mocked_livisi_controller,
    mocked_livisi_login,
    mocked_livisi_setup_entry,
)

from tests.common import MockConfigEntry


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

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
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
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == expected_reason
    with mocked_livisi_login(), mocked_livisi_controller(), mocked_livisi_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_CONFIG,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""
    entry: MockConfigEntry = create_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with mocked_livisi_login(), mocked_livisi_controller(), mocked_livisi_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_CONFIG
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
