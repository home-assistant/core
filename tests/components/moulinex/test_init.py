"""Tests for the Moulinex integration setup."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiomoulinex import (
    ApplianceState,
    Firmware,
    MoulinexAuthenticationError,
    MoulinexConnectionError,
    MoulinexError,
    TokensUpdated,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.moulinex.const import CONF_TOKENS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import push_event, push_state, setup_integration
from .conftest import COOKEO_ID, build_tokens, load_status

COOKEO_ENTITY_ID = "sensor.cookeo_touch_wifi"


async def test_setup_unload(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The integration connects on setup and disconnects on unload."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_moulinex_client.connect.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_moulinex_client.add_listener.return_value.assert_called_once()
    mock_moulinex_client.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(MoulinexConnectionError("timeout"), id="cannot_connect"),
        pytest.param(MoulinexError("unexpected"), id="unexpected_answer"),
    ],
)
async def test_setup_retries_when_cloud_fails(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """The setup is retried when the cloud can not be reached."""
    mock_moulinex_client.connect.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_moulinex_client.add_listener.return_value.assert_called_once()


async def test_events_received_while_connecting(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The tokens and states the client sends while it connects are used."""
    tokens = build_tokens(refresh_token="refresh-2")
    state = replace(
        mock_moulinex_client.states[COOKEO_ID],
        status=load_status("status_cooking.json"),
    )

    async def connect() -> None:
        push_event(mock_moulinex_client, TokensUpdated(tokens))
        push_state(mock_moulinex_client, COOKEO_ID, state)

    mock_moulinex_client.connect.side_effect = connect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_TOKENS] == tokens.to_dict()
    assert hass.states.get(COOKEO_ENTITY_ID).state == "cooking"


@pytest.mark.usefixtures("mock_moulinex_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device of every appliance."""
    await setup_integration(hass, mock_config_entry)

    assert (
        sorted(
            dr.async_entries_for_config_entry(
                device_registry, mock_config_entry.entry_id
            ),
            key=lambda device: sorted(device.identifiers),
        )
        == snapshot
    )


async def test_setup_fails_when_tokens_refused(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The setup fails as an authentication error when the tokens are refused."""
    mock_moulinex_client.connect.side_effect = MoulinexAuthenticationError("refused")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "could not authenticate" in caplog.text


async def test_renewed_tokens_are_stored(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The tokens renewed by the client are stored in the config entry."""
    await setup_integration(hass, mock_config_entry)
    tokens = build_tokens(refresh_token="refresh-2")

    push_event(mock_moulinex_client, TokensUpdated(tokens))

    assert mock_config_entry.data[CONF_TOKENS] == tokens.to_dict()


async def test_firmware_update(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A new firmware version is shown on the device, an unknown one is ignored."""
    await setup_integration(hass, mock_config_entry)
    state = mock_moulinex_client.states[COOKEO_ID]

    push_state(mock_moulinex_client, COOKEO_ID, ApplianceState(status=state.status))

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, COOKEO_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "5.0.54"

    push_state(
        mock_moulinex_client,
        COOKEO_ID,
        replace(
            state,
            shadow=replace(state.shadow, firmware=Firmware(ui_version="5.1.0")),
        ),
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, COOKEO_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "5.1.0"
