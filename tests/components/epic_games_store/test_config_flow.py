"""Test the Epic Games Store config flow."""

from http.client import HTTPException
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.epic_games_store.config_flow import get_default_language
from homeassistant.components.epic_games_store.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    DATA_ERROR_ATTRIBUTE_NOT_FOUND,
    DATA_ERROR_WRONG_COUNTRY,
    DATA_FREE_GAMES,
    MOCK_COUNTRY,
    MOCK_LANGUAGE,
)


async def test_default_language(hass: HomeAssistant) -> None:
    """Test we get the form."""
    hass.config.language = "fr"
    hass.config.country = "FR"
    assert get_default_language(hass) == "fr"

    hass.config.language = "es"
    hass.config.country = "ES"
    assert get_default_language(hass) == "es-ES"

    hass.config.language = "en"
    hass.config.country = "AZ"
    assert get_default_language(hass) is None


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.epic_games_store.config_flow.EpicGamesStoreAPI.get_free_games",
        return_value=DATA_FREE_GAMES,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LANGUAGE: MOCK_LANGUAGE,
                CONF_COUNTRY: MOCK_COUNTRY,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["result"].unique_id == f"freegames-{MOCK_LANGUAGE}-{MOCK_COUNTRY}"
    assert (
        result2["title"]
        == f"Epic Games Store - Free Games ({MOCK_LANGUAGE}-{MOCK_COUNTRY})"
    )
    assert result2["data"] == {
        CONF_LANGUAGE: MOCK_LANGUAGE,
        CONF_COUNTRY: MOCK_COUNTRY,
    }


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epic_games_store.config_flow.EpicGamesStoreAPI.get_free_games",
        side_effect=HTTPException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LANGUAGE: MOCK_LANGUAGE,
                CONF_COUNTRY: MOCK_COUNTRY,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_cannot_connect_wrong_param(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epic_games_store.config_flow.EpicGamesStoreAPI.get_free_games",
        return_value=DATA_ERROR_WRONG_COUNTRY,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LANGUAGE: MOCK_LANGUAGE,
                CONF_COUNTRY: MOCK_COUNTRY,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_service_error(hass: HomeAssistant) -> None:
    """Test we handle service error gracefully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epic_games_store.config_flow.EpicGamesStoreAPI.get_free_games",
        return_value=DATA_ERROR_ATTRIBUTE_NOT_FOUND,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LANGUAGE: MOCK_LANGUAGE,
                CONF_COUNTRY: MOCK_COUNTRY,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["result"].unique_id == f"freegames-{MOCK_LANGUAGE}-{MOCK_COUNTRY}"
    assert (
        result2["title"]
        == f"Epic Games Store - Free Games ({MOCK_LANGUAGE}-{MOCK_COUNTRY})"
    )
    assert result2["data"] == {
        CONF_LANGUAGE: MOCK_LANGUAGE,
        CONF_COUNTRY: MOCK_COUNTRY,
    }
