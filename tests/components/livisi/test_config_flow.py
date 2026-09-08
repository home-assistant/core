"""Test the Livisi Home Assistant config flow."""

from unittest.mock import patch

from livisi import (
    ErrorCodeException,
    IncorrectIpAddressException,
    LivisiException,
    ShcUnreachableException,
    WrongCredentialException,
)
import pytest

from homeassistant.components.livisi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_CONFIG, mocked_livisi_connect, mocked_livisi_setup_entry


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test create LIVISI entity."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with mocked_livisi_connect() as connect, mocked_livisi_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "SHC Classic"
        assert result["data"]["host"] == "1.1.1.1"
        assert result["data"]["password"] == "test"
        connect.assert_awaited_once_with("1.1.1.1", "test")
        connect.return_value.close.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("exception", "expected_reason"),
    [
        (ShcUnreachableException(), "cannot_connect"),
        (IncorrectIpAddressException(), "wrong_ip_address"),
        (WrongCredentialException(), "wrong_password"),
        (ErrorCodeException(1000), "cannot_connect"),
        (LivisiException(), "cannot_connect"),
    ],
)
async def test_create_entity_after_login_error(
    hass: HomeAssistant, exception: LivisiException, expected_reason: str
) -> None:
    """Test LIVISI can create an entity after user login errors."""
    with patch(
        "homeassistant.components.livisi.config_flow.livisi_connect",
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
    with mocked_livisi_connect(), mocked_livisi_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_CONFIG,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
