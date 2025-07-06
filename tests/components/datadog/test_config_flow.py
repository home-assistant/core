"""Tests for the Datadog config flow."""

from unittest import mock
from unittest.mock import patch

import pytest

from homeassistant.components import datadog
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .common import MOCK_CONFIG

from tests.common import EVENT_STATE_CHANGED, MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""
    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == MOCK_CONFIG


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure."""
    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": "user"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import triggers config flow and is accepted."""
    with patch(
        "homeassistant.components.datadog.config_flow.validate_datadog_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN,
            context={"source": "import"},
            data=MOCK_CONFIG,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == MOCK_CONFIG


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options after setup."""
    mock_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_CONFIG,
        unique_id="datadog_unique",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    new_config = {
        "host": "127.0.0.1",
        "port": 8126,
        "prefix": "updated",
        "rate": 5,
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=new_config
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == new_config


@pytest.mark.asyncio
async def test_validate_connection_success() -> None:
    """Test validate_datadog_connection succeeds."""
    client = mock.MagicMock()
    assert await datadog.validate_datadog_connection(client)
    client.increment.assert_called_once_with("connection_test")


@pytest.mark.asyncio
async def test_validate_connection_oserror() -> None:
    """Test validate_datadog_connection fails with OSError."""
    client = mock.MagicMock()
    client.increment.side_effect = OSError
    assert not await datadog.validate_datadog_connection(client)


@pytest.mark.asyncio
async def test_validate_connection_valueerror() -> None:
    """Test validate_datadog_connection fails with ValueError."""
    client = mock.MagicMock()
    client.increment.side_effect = ValueError
    assert not await datadog.validate_datadog_connection(client)


@pytest.mark.asyncio
async def test_state_changed_skips_unknown(hass: HomeAssistant) -> None:
    """Test state_changed_listener skips None and unknown states."""
    with (
        patch("homeassistant.components.datadog.initialize"),
        patch("homeassistant.components.datadog.DogStatsd") as mock_statsd,
    ):
        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "prefix": "ha",
                    "rate": 1,
                }
            },
        )

        # Test None state
        hass.bus.async_fire(EVENT_STATE_CHANGED, {"new_state": None})
        await hass.async_block_till_done()
        assert not mock_statsd.gauge.called

        # Test STATE_UNKNOWN
        unknown_state = mock.MagicMock()
        unknown_state.state = STATE_UNKNOWN
        hass.bus.async_fire(EVENT_STATE_CHANGED, {"new_state": unknown_state})
        await hass.async_block_till_done()
        assert not mock_statsd.gauge.called
