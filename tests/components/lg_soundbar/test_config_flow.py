"""Test the lg_soundbar config flow."""

from typing import Any
from unittest.mock import AsyncMock

from aiotemescal import TemescalConnectionError, TemescalTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lg_soundbar.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import set_answers

USER_INPUT = {CONF_HOST: "1.1.1.1"}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "answers",
    [
        pytest.param(
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {"s_uuid": "uuid"},
            },
            id="uuid_in_mac_info",
        ),
        pytest.param(
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "PRODUCT_INFO": {"s_uuid": "uuid"},
            },
            id="no_mac_info",
        ),
        pytest.param(
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {},
                "PRODUCT_INFO": {"s_uuid": "uuid"},
            },
            id="uuid_missing_from_mac_info",
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, mock_client: AsyncMock, answers: dict[str, Any]
) -> None:
    """Test creating an entry, wherever the device reports its uuid."""
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "name"
    assert result["result"].unique_id == "uuid"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_without_uuid(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test creating an entry for a device that never reports its uuid."""
    set_answers(mock_client, {"SPK_LIST_VIEW_INFO": {"s_user_name": "name"}})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "name"
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "answers", "error"),
    [
        pytest.param(
            TemescalConnectionError, {}, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(TemescalTimeoutError, {}, "cannot_connect", id="connect_timeout"),
        pytest.param(
            None, {"MAC_INFO_DEV": {"s_uuid": "uuid"}}, "no_data", id="no_name"
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    side_effect: type[Exception] | None,
    answers: dict[str, Any],
    error: str,
) -> None:
    """Test errors are reported and the flow can recover from them."""
    mock_client.__aenter__.side_effect = side_effect
    original_request = mock_client.request.side_effect
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.__aenter__.side_effect = None
    mock_client.request.side_effect = original_request

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("unique_id", "answers"),
    [
        pytest.param(
            "uuid",
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {"s_uuid": "uuid"},
            },
            id="same_uuid",
        ),
        pytest.param(
            None,
            {"SPK_LIST_VIEW_INFO": {"s_user_name": "name"}},
            id="same_host_without_uuid",
        ),
    ],
)
async def test_already_configured(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    unique_id: str | None,
    answers: dict[str, Any],
) -> None:
    """Test a device is not added twice."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT},
        unique_id=unique_id,
    ).add_to_hass(hass)
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
