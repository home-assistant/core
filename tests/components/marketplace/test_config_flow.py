"""Tests for the Marketplace config flow."""

import asyncio
from unittest.mock import AsyncMock

from aiogithubapi import GitHubException
import pytest

from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from .const import TOKEN

from tests.common import MockConfigEntry


async def _start_device_step(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Start connecting a GitHub account and return the flow id at the device step."""
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    return result["flow_id"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_system_flow(hass: HomeAssistant) -> None:
    """Test the system flow sets up the Marketplace without a GitHub account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {}
    assert result["options"] == {}


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("warning_accepted", [None])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_connect_github(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test connecting a GitHub account stores the token on the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    # First what connecting does and why, GitHub is asked for a code after it
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    github_device_client.register.assert_not_called()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "wait_for_device"
    assert result["description_placeholders"] == {
        "url": "https://github.com/login/device",
        "code": "WDJB-MJHT",
    }

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_TOKEN: TOKEN}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_registration_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
) -> None:
    """Test the flow aborts when the device can not be registered."""
    github_device_client.register.side_effect = GitHubException("Registration failed")

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_registration_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
) -> None:
    """Test the flow aborts when the registration carries no device code."""
    registration = AsyncMock()
    registration.data = None
    github_device_client.register.return_value = registration

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_activation_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the flow aborts when the device activation fails."""

    async def mock_activation(device_code: str) -> None:
        """Fail once the test releases the activation."""
        await device_activation_event.wait()
        raise GitHubException("Activation failed")

    github_device_client.activation = mock_activation

    flow_id = await _start_device_step(hass, mock_config_entry)

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "activation_failed"


@pytest.mark.parametrize(
    ("invalid_answers", "reason"),
    [
        pytest.param(1, "reconfigure_successful", id="valid_on_the_next_poll"),
        pytest.param(3, "activation_failed", id="stays_invalid"),
    ],
)
@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_activation_asks_again_for_an_unknown_device_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
    invalid_answers: int,
    reason: str,
) -> None:
    """Test GitHub not knowing the code right after a quick approval is retried."""
    github_device_client.register.return_value.data.interval = 0
    answered = github_device_client.activation
    calls = 0

    async def mock_activation(device_code: str) -> AsyncMock:
        """Answer like GitHub does when the approval was quick."""
        nonlocal calls
        calls += 1
        if calls <= invalid_answers:
            raise GitHubException("The device_code provided is not valid.")
        return await answered(device_code)

    github_device_client.activation = mock_activation

    flow_id = await _start_device_step(hass, mock_config_entry)

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert calls == min(invalid_answers + 1, 3)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_activation_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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

    flow_id = await _start_device_step(hass, mock_config_entry)

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_remove_while_activating(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_device_client: AsyncMock,
) -> None:
    """Test the flow can be cancelled while waiting for the device."""
    flow_id = await _start_device_step(hass, mock_config_entry)

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
        DOMAIN, context={"source": SOURCE_SYSTEM}
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


async def test_no_options_flow(init_integration: MockConfigEntry) -> None:
    """Test the Marketplace has no options to set."""
    assert init_integration.supports_options is False
