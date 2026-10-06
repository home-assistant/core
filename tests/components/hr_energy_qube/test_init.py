"""Test the Qube Heat Pump integration init."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from python_qube_heatpump import QubeDeviceInfo

from homeassistant.components.hr_energy_qube.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import DEVICE_INFO, setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_qube_client.close.assert_called_once()


@pytest.mark.parametrize(
    ("connect_result", "connect_error"),
    [
        (False, None),
        (None, OSError("Connection refused")),
    ],
)
async def test_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    connect_result: bool | None,
    connect_error: Exception | None,
) -> None:
    """Test setup failure when the device cannot be reached."""
    if connect_error is not None:
        mock_qube_client.connect.side_effect = connect_error
    else:
        mock_qube_client.connect.return_value = connect_result

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        mock_config_entry.reason == "Unable to connect to the Qube heat pump at 1.2.3.4"
    )
    mock_qube_client.close.assert_called_once()


@pytest.mark.parametrize(
    ("device_info", "unique_id"),
    [(DEVICE_INFO, DEVICE_INFO.uuid), (None, None)],
    ids=["mdns", "no_mdns"],
)
async def test_unique_id_set_after_setup(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_info: QubeDeviceInfo | None,
    unique_id: str | None,
) -> None:
    """Test an entry created without a unique id gets the controller's uuid."""
    mock_device_info.return_value = device_info

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.unique_id == unique_id


async def test_unique_id_not_looked_up_when_set(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
) -> None:
    """Test entries that already have a unique id skip the mDNS lookup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    )

    await setup_integration(hass, entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_device_info.assert_not_awaited()


async def test_unique_id_not_set_when_taken(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the uuid is not set when another entry already has it."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "qube.local", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    mock_device_info.return_value = DEVICE_INFO

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.unique_id is None
