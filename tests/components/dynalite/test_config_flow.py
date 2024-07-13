"""Test Dynalite config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dynalite
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("first_con", "second_con", "exp_type", "exp_result", "exp_reason"),
    [
        (True, True, "create_entry", ConfigEntryState.LOADED, ""),
        (False, False, "abort", None, "cannot_connect"),
        (True, False, "create_entry", ConfigEntryState.SETUP_RETRY, ""),
    ],
)
async def test_flow(
    hass: HomeAssistant,
    first_con,
    second_con,
    exp_type,
    exp_result,
    exp_reason,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Run a flow with or without errors and return result."""
    issue = issue_registry.async_get_issue(dynalite.DOMAIN, "deprecated_yaml")
    assert issue is None
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        side_effect=[first_con, second_con],
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host},
        )
        await hass.async_block_till_done()
    assert result["type"] == exp_type
    if exp_result:
        assert result["result"].state == exp_result
    if exp_reason:
        assert result["reason"] == exp_reason
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{dynalite.DOMAIN}"
    )
    assert issue is not None
    assert issue.issue_domain == dynalite.DOMAIN
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Check that deprecation warning appears in caplog."""
    await async_setup_component(
        hass, dynalite.DOMAIN, {dynalite.DOMAIN: {dynalite.CONF_HOST: "aaa"}}
    )
    assert "The 'dynalite' option is deprecated" in caplog.text


async def test_existing(hass: HomeAssistant) -> None:
    """Test when the entry exists with the same config."""
    host = "1.2.3.4"
    MockConfigEntry(
        domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host}
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_existing_update(hass: HomeAssistant) -> None:
    """Test when the entry exists with a different config."""
    host = "1.2.3.4"
    port1 = 7777
    port2 = 8888
    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={dynalite.CONF_HOST: host, CONF_PORT: port1},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices"
    ) as mock_dyn_dev:
        mock_dyn_dev().async_setup = AsyncMock(return_value=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_dyn_dev().configure.assert_called_once()
        assert mock_dyn_dev().configure.mock_calls[0][1][0]["port"] == port1
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host, CONF_PORT: port2},
        )
        await hass.async_block_till_done()
        assert mock_dyn_dev().configure.call_count == 2
        assert mock_dyn_dev().configure.mock_calls[1][1][0]["port"] == port2
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_two_entries(hass: HomeAssistant) -> None:
    """Test when two different entries exist with different hosts."""
    host1 = "1.2.3.4"
    host2 = "5.6.7.8"
    MockConfigEntry(
        domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host1}
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host2},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].state is ConfigEntryState.LOADED


async def test_setup_user(hass: HomeAssistant) -> None:
    """Test configuration via the user flow."""
    host = "3.4.5.6"
    port = 1234
    result = await hass.config_entries.flow.async_init(
        dynalite.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": host, "port": port},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].state is ConfigEntryState.LOADED
    assert result["title"] == host
    assert result["data"] == {
        "host": host,
        "port": port,
    }


async def test_setup_user_existing_host(hass: HomeAssistant) -> None:
    """Test that when we setup a host that is defined, we get an error."""
    host = "3.4.5.6"
    MockConfigEntry(
        domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        dynalite.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": host, "port": 1234},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
