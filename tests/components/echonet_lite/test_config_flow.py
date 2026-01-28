"""Tests for the ECHONET Lite config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.echonet_lite.const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
    CONF_POLL_INTERVAL,
    DEFAULT_INTERFACE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_echonet_lite_client")


async def test_user_flow_success(
    hass: HomeAssistant, mock_async_validate_network: AsyncMock
) -> None:
    """Test the happy path of the user initiated config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {
        CONF_INTERFACE: DEFAULT_INTERFACE,
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_ENABLE_EXPERIMENTAL: False,
    }


async def test_user_flow_with_custom_interface(
    hass: HomeAssistant, mock_async_validate_network: AsyncMock
) -> None:
    """Test user flow with a custom interface selection."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "10.10.10.10"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {
        CONF_INTERFACE: "10.10.10.10",
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_ENABLE_EXPERIMENTAL: False,
    }


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test errors are surfaced when the socket cannot bind."""

    with patch(
        "homeassistant.components.echonet_lite.config_flow.create_multicast_socket",
        AsyncMock(side_effect=OSError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_single_instance_abort(hass: HomeAssistant) -> None:
    """Ensure only a single config entry can exist."""

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_async_validate_network: AsyncMock
) -> None:
    """Test reconfiguring an existing entry changes interface only."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_INTERFACE: "192.168.1.50",
            CONF_POLL_INTERVAL: 120,
            CONF_ENABLE_EXPERIMENTAL: True,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Change interface to a new value, other options should be preserved
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "10.10.10.10"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # Interface changed, but other options preserved
    assert entry.options == {
        CONF_INTERFACE: "10.10.10.10",
        CONF_POLL_INTERVAL: 120,
        CONF_ENABLE_EXPERIMENTAL: True,
    }


async def test_integration_discovery_creates_entry(
    hass: HomeAssistant, mock_async_validate_network: AsyncMock
) -> None:
    """Test the automatic flow path used during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {
        CONF_INTERFACE: DEFAULT_INTERFACE,
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_ENABLE_EXPERIMENTAL: False,
    }


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_echonet_lite_client,
) -> None:
    """Test the options flow for poll interval and experimental device classes."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_POLL_INTERVAL: 120,
            CONF_ENABLE_EXPERIMENTAL: True,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Interface should be preserved from original config
    assert mock_config_entry.options[CONF_INTERFACE] == DEFAULT_INTERFACE
    assert mock_config_entry.options[CONF_POLL_INTERVAL] == 120
    assert mock_config_entry.options[CONF_ENABLE_EXPERIMENTAL] is True


async def test_options_flow_preserves_interface(
    hass: HomeAssistant,
    mock_echonet_lite_client,
) -> None:
    """Test options flow preserves the interface setting."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_INTERFACE: "192.168.1.100",
            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
            CONF_ENABLE_EXPERIMENTAL: False,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_POLL_INTERVAL: 90,
            CONF_ENABLE_EXPERIMENTAL: True,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Interface should be preserved
    assert entry.options[CONF_INTERFACE] == "192.168.1.100"
    assert entry.options[CONF_POLL_INTERVAL] == 90
    assert entry.options[CONF_ENABLE_EXPERIMENTAL] is True


async def test_user_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test unknown error is surfaced when unexpected exception occurs."""
    with patch(
        "homeassistant.components.echonet_lite.config_flow.create_multicast_socket",
        AsyncMock(side_effect=RuntimeError("Unexpected error")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
