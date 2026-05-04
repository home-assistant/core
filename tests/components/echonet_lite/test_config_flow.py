"""Tests for the ECHONET Lite config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.echonet_lite.const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
    DEFAULT_INTERFACE,
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
    assert result["data"] == {CONF_INTERFACE: DEFAULT_INTERFACE}
    assert result["options"] == {
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
    assert result["data"] == {CONF_INTERFACE: "10.10.10.10"}
    assert result["options"] == {
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
        data={CONF_INTERFACE: "192.168.1.50"},
        options={
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
    # Interface changed in data, options preserved
    assert entry.data == {CONF_INTERFACE: "10.10.10.10"}
    assert entry.options == {
        CONF_ENABLE_EXPERIMENTAL: True,
    }


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_echonet_lite_client,
) -> None:
    """Test the options flow for experimental device classes."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENABLE_EXPERIMENTAL: True,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Interface remains in data, options only has experimental flag
    assert mock_config_entry.data[CONF_INTERFACE] == DEFAULT_INTERFACE
    assert mock_config_entry.options[CONF_ENABLE_EXPERIMENTAL] is True


async def test_options_flow_preserves_interface(
    hass: HomeAssistant,
    mock_echonet_lite_client,
) -> None:
    """Test options flow does not affect interface in data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INTERFACE: "192.168.1.100"},
        options={
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
            CONF_ENABLE_EXPERIMENTAL: True,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Interface remains in data, unaffected by options flow
    assert entry.data[CONF_INTERFACE] == "192.168.1.100"
    assert entry.options[CONF_ENABLE_EXPERIMENTAL] is True
