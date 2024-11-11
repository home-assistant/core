"""Test the Nord Pool config flow."""

from __future__ import annotations

from dataclasses import replace
from http import HTTPStatus
from unittest.mock import patch

from pynordpool import API, DeliveryPeriodData
import pytest

from homeassistant import config_entries
from homeassistant.components.nordpool.const import CONF_AREAS, DOMAIN
from homeassistant.const import CONF_CURRENCY, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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
    ("status", "p_error"),
    [
        (HTTPStatus.UNAUTHORIZED, "cannot_connect"),
        (HTTPStatus.FORBIDDEN, "cannot_connect"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "cannot_connect"),
        (HTTPStatus.NO_CONTENT, "cannot_connect"),
    ],
)
async def test_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    load_data: str,
    status: HTTPStatus,
    p_error: str,
) -> None:
    """Test cannot connect error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    aioclient_mock.request(
        "get",
        API + "/DayAheadPrices",
        text=load_data,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=status,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG,
    )

    assert result["errors"] == {"base": p_error}

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "get",
        API + "/DayAheadPrices",
        text=load_data,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )

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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nord Pool"
    assert result["data"] == {"areas": ["SE3", "SE4"], "currency": "SEK"}


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_reconfigure(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    get_data: DeliveryPeriodData,
) -> None:
    """Test reconfiguration."""

    result = await load_int.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AREAS: ["SE3"],
            CONF_CURRENCY: "EUR",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert load_int.data == {
        "areas": [
            "SE3",
        ],
        "currency": "EUR",
    }


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
@pytest.mark.parametrize(
    ("status", "p_error"),
    [
        (HTTPStatus.UNAUTHORIZED, "cannot_connect"),
        (HTTPStatus.FORBIDDEN, "cannot_connect"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "cannot_connect"),
        (HTTPStatus.NO_CONTENT, "cannot_connect"),
    ],
)
async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    load_data: str,
    load_int: MockConfigEntry,
    get_data: DeliveryPeriodData,
    status: HTTPStatus,
    p_error: str,
) -> None:
    """Test cannot connect error in a reeconfigure flow."""

    result = await load_int.start_reconfigure_flow(hass)

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "get",
        API + "/DayAheadPrices",
        text=load_data,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=status,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_AREAS: ["SE3"],
            CONF_CURRENCY: "EUR",
        },
    )

    assert result["errors"] == {"base": p_error}

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "get",
        API + "/DayAheadPrices",
        text=load_data,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_AREAS: ["SE3"],
            CONF_CURRENCY: "EUR",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert load_int.data == {
        "areas": [
            "SE3",
        ],
        "currency": "EUR",
    }
