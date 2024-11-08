"""Test the Nord Pool config flow."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from pynordpool import (
    DeliveryPeriodData,
    NordPoolAuthenticationError,
    NordPoolConnectionError,
    NordPoolError,
    NordPoolResponseError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ENTRY_CONFIG


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_form(hass: HomeAssistant, get_data: DeliveryPeriodData) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            return_value=get_data,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["title"] == "Nord Pool"
    assert result["data"] == {"areas": ["SE3", "SE4"], "currency": "SEK"}


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_single_config_entry(
    hass: HomeAssistant, load_int: None, get_data: DeliveryPeriodData
) -> None:
    """Test abort for single config entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
@pytest.mark.parametrize(
    ("error_message", "p_error"),
    [
        (NordPoolConnectionError, "cannot_connect"),
        (NordPoolAuthenticationError, "cannot_connect"),
        (NordPoolError, "cannot_connect"),
        (NordPoolResponseError, "cannot_connect"),
    ],
)
async def test_cannot_connect(
    hass: HomeAssistant,
    get_data: DeliveryPeriodData,
    error_message: Exception,
    p_error: str,
) -> None:
    """Test cannot connect error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
        side_effect=error_message,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result["errors"] == {"base": p_error}

    with patch(
        "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
        return_value=get_data,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nord Pool"
    assert result["data"] == {"areas": ["SE3", "SE4"], "currency": "SEK"}


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_empty_data(hass: HomeAssistant, get_data: DeliveryPeriodData) -> None:
    """Test empty data error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    invalid_data = replace(get_data, raw={})

    with patch(
        "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
        return_value=invalid_data,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result["errors"] == {"base": "no_data"}

    with patch(
        "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
        return_value=get_data,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nord Pool"
    assert result["data"] == {"areas": ["SE3", "SE4"], "currency": "SEK"}
