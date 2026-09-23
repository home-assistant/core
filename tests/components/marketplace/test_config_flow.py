"""Tests for the Marketplace config flow."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

from aiogithubapi import GitHubException
import pytest
import voluptuous as vol

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from .const import TOKEN

from tests.common import MockConfigEntry

ACKNOWLEDGEMENTS = {
    "acc_addons": True,
    "acc_disable": True,
    "acc_logs": True,
    "acc_untested": True,
}


async def _start_device_step(hass: HomeAssistant) -> str:
    """Walk the acknowledgement form and return the flow id at the device step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ACKNOWLEDGEMENTS
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    return result["flow_id"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the full manual user flow from start to finish."""
    flow_id = await _start_device_step(hass)

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {CONF_TOKEN: TOKEN}
    assert result["options"] == {}


@pytest.mark.parametrize(
    "acknowledgement",
    [
        pytest.param("acc_addons", id="addons"),
        pytest.param("acc_disable", id="disable"),
        pytest.param("acc_logs", id="logs"),
        pytest.param("acc_untested", id="untested"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_all_acknowledgements_required(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
    acknowledgement: str,
) -> None:
    """Test the flow stays on the form until every statement is acknowledged."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**ACKNOWLEDGEMENTS, acknowledgement: False},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "acc"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_registration_failure(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
) -> None:
    """Test the flow aborts when the device can not be registered."""
    github_device_client.register.side_effect = GitHubException("Registration failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ACKNOWLEDGEMENTS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_registration_without_data(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
) -> None:
    """Test the flow aborts when the registration carries no device code."""
    registration = AsyncMock()
    registration.data = None
    github_device_client.register.return_value = registration

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ACKNOWLEDGEMENTS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_activation_failure(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the flow aborts when the device activation fails."""

    async def mock_activation(device_code: str) -> None:
        """Fail once the test releases the activation."""
        await device_activation_event.wait()
        raise GitHubException("Activation failed")

    github_device_client.activation = mock_activation

    flow_id = await _start_device_step(hass)

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_activation_without_data(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the flow aborts when the activation carries no access token."""

    async def mock_activation(device_code: str) -> AsyncMock:
        """Return an activation without data."""
        await device_activation_event.wait()
        activation = AsyncMock()
        activation.data = None
        return activation

    github_device_client.activation = mock_activation

    flow_id = await _start_device_step(hass)

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_remove_while_activating(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
) -> None:
    """Test the flow can be cancelled while waiting for the device."""
    flow_id = await _start_device_step(hass)

    assert hass.config_entries.flow.async_get(flow_id)

    hass.config_entries.flow._async_remove_flow_progress(flow_id)
    await hass.async_block_till_done()

    with pytest.raises(UnknownFlow):
        hass.config_entries.flow.async_get(flow_id)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow aborts when an entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test reauthentication replaces the token on the existing entry."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={CONF_TOKEN: "expired"}
    )

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_TOKEN: TOKEN}


async def test_options_flow(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    init_integration: MockConfigEntry,
) -> None:
    """Test the options flow."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    schema: dict[vol.Marker, Any] = result["data_schema"].schema
    assert {str(key): key.default() for key in schema} == {
        "appdaemon": True,
        "country": "ALL",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"appdaemon": False, "country": "NL"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {
        "appdaemon": False,
        "country": "NL",
    }
    assert init_integration.data == {CONF_TOKEN: TOKEN}

    # The entry is reloaded, so the Marketplace picks the new options up
    marketplace = init_integration.runtime_data
    assert marketplace.configuration.appdaemon is False
    assert marketplace.configuration.country == "NL"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_not_set_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow aborts when the Marketplace is not set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_setup"


async def test_options_flow_pending_tasks(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    init_integration: MockConfigEntry,
) -> None:
    """Test the options flow aborts while the Marketplace still has work queued."""
    marketplace.queue.add(asyncio.sleep(0))

    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "pending_tasks"

    # Drain the queue so the entry can be unloaded again
    await marketplace.queue.execute()
