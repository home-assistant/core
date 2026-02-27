"""Test integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT

from homeassistant.components.madvr.const import (
    DOMAIN,
    SERVICE_ACTIVATE_PROFILE,
    SERVICE_PRESS_KEY,
    SERVICE_RUN_ACTION,
)


async def test_setup_and_unload_entry(hass, mock_config_entry, mock_envy_client):
    """Test setup and unload lifecycle."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.madvr.MadvrEnvyClient", return_value=mock_envy_client),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ) as mock_forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ) as mock_unload,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        runtime_data = mock_config_entry.runtime_data
        assert runtime_data.client is mock_envy_client
        assert runtime_data.coordinator.data is not None
        assert runtime_data.coordinator.data["power_state"] == "on"
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]
        assert hass.services.has_service(DOMAIN, SERVICE_PRESS_KEY)
        assert hass.services.has_service(DOMAIN, SERVICE_ACTIVATE_PROFILE)
        assert hass.services.has_service(DOMAIN, SERVICE_RUN_ACTION)

        mock_forward.assert_awaited_once()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        mock_unload.assert_awaited_once()
        assert DOMAIN not in hass.data
        assert not hass.services.has_service(DOMAIN, SERVICE_PRESS_KEY)
        assert not hass.services.has_service(DOMAIN, SERVICE_ACTIVATE_PROFILE)
        assert not hass.services.has_service(DOMAIN, SERVICE_RUN_ACTION)

    mock_envy_client.start.assert_called_once()
    assert mock_envy_client.stop.await_count >= 1


async def test_setup_entry_not_ready_on_sync_timeout(hass, mock_config_entry, mock_envy_client):
    """Test setup fails gracefully if initial sync times out."""
    mock_envy_client.wait_synced.side_effect = TimeoutError
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.madvr.MadvrEnvyClient", return_value=mock_envy_client),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_envy_client.stop.await_count >= 1


async def test_setup_entry_uses_options_for_timeouts(hass, mock_envy_client):
    """Test entry options are used to construct client."""
    from tests.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="madVR Envy",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 44077},
        options={
            "connect_timeout": 5.0,
            "command_timeout": 4.0,
            "read_timeout": 15.0,
            "sync_timeout": 12.0,
            "reconnect_initial_backoff": 0.5,
            "reconnect_max_backoff": 8.0,
            "reconnect_jitter": 0.1,
        },
        unique_id="madvr_192.168.1.100_44077",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.madvr.MadvrEnvyClient", return_value=mock_envy_client
        ) as mock_client_class,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    kwargs = mock_client_class.call_args.kwargs
    assert kwargs["connect_timeout"] == 5.0
    assert kwargs["command_timeout"] == 4.0
    assert kwargs["read_timeout"] == 15.0
