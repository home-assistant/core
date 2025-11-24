"""Test the Essent config flow."""

from __future__ import annotations

from unittest.mock import patch

from essent_dynamic_pricing import (
    EssentConnectionError,
    EssentDataError,
    EssentResponseError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.essent.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we can create an entry."""
    with (
        patch(
            "homeassistant.components.essent.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.essent.config_flow.EssentClient.async_get_prices",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Essent"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (EssentConnectionError(), "cannot_connect"),
        (EssentResponseError("bad"), "cannot_connect"),
        (EssentDataError("bad"), "invalid_data"),
        (Exception(), "unknown"),
    ],
)
async def test_cannot_connect(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test connection errors show form with error."""
    with patch(
        "homeassistant.components.essent.config_flow.EssentClient.async_get_prices",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == error
