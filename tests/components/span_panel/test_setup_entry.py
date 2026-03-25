"""Tests for Span Panel async_setup_entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from span_panel_api.exceptions import SpanPanelAuthError

from homeassistant.components.span_panel import SpanPanelRuntimeData, async_setup_entry
from homeassistant.components.span_panel.const import (
    CONF_API_VERSION,
    CONF_EBUS_BROKER_HOST,
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_PORT,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HTTP_PORT,
    DOMAIN,
)
from homeassistant.config_entries import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .factories import SpanPanelSnapshotFactory

from tests.common import MockConfigEntry


def _create_v2_entry(**data_overrides) -> MockConfigEntry:
    """Create a standard v2 config entry for setup-entry tests."""
    data = {
        CONF_API_VERSION: "v2",
        CONF_HOST: "192.168.1.50",
        CONF_EBUS_BROKER_HOST: "span-panel.local",
        CONF_EBUS_BROKER_USERNAME: "mqtt-user",
        CONF_EBUS_BROKER_PASSWORD: "mqtt-pass",
        CONF_EBUS_BROKER_PORT: 8883,
        CONF_HTTP_PORT: 80,
    }
    data.update(data_overrides)
    return MockConfigEntry(
        domain=DOMAIN,
        data=data,
        entry_id="entry-setup",
        title="sp3-setup-001",
        unique_id="sp3-setup-001",
    )


async def test_async_setup_entry_v2_success_sets_runtime_data_and_title(
    hass: HomeAssistant,
) -> None:
    """Successful v2 setup should register runtime data and normalize the title."""
    entry = _create_v2_entry()
    entry.add_to_hass(hass)
    snapshot = SpanPanelSnapshotFactory.create(serial_number="sp3-setup-001")
    client = MagicMock()
    client.connect = AsyncMock()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_setup_streaming = AsyncMock()
    coordinator.data = snapshot

    with (
        patch("homeassistant.components.span_panel.async_register_commands") as mock_ws,
        patch(
            "homeassistant.components.span_panel.SpanMqttClient", return_value=client
        ) as mock_client_cls,
        patch(
            "homeassistant.components.span_panel.SpanPanelCoordinator",
            return_value=coordinator,
        ) as mock_coordinator_cls,
        patch(
            "homeassistant.components.span_panel.ensure_device_registered",
            AsyncMock(),
        ) as mock_ensure_device,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        ) as mock_forward,
        patch.object(hass.config_entries, "async_update_entry") as mock_update_entry,
    ):
        assert await async_setup_entry(hass, entry) is True

    assert entry.runtime_data == SpanPanelRuntimeData(coordinator=coordinator)
    assert hass.data[DOMAIN]["websocket_registered"] is True
    mock_ws.assert_called_once_with(hass)
    mock_client_cls.assert_called_once()
    client.connect.assert_awaited_once()
    mock_coordinator_cls.assert_called_once_with(hass, client, entry)
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    coordinator.async_setup_streaming.assert_awaited_once()
    mock_ensure_device.assert_awaited_once_with(hass, entry, snapshot, "SPAN Panel")
    mock_forward.assert_awaited_once()
    mock_update_entry.assert_called_once_with(entry, title="SPAN Panel")


async def test_async_setup_entry_v2_missing_mqtt_credentials_raises_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Missing v2 MQTT credentials should trigger reauthentication."""
    entry = _create_v2_entry(**{CONF_EBUS_BROKER_PASSWORD: None})
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.span_panel.async_register_commands"),
        patch("homeassistant.components.span_panel.SpanMqttClient") as mock_client_cls,
        pytest.raises(ConfigEntryAuthFailed, match="missing MQTT credentials"),
    ):
        await async_setup_entry(hass, entry)

    mock_client_cls.assert_not_called()


async def test_async_setup_entry_v2_missing_unique_id_raises_not_ready(
    hass: HomeAssistant,
) -> None:
    """A v2 entry without a serial-number unique ID should not set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_VERSION: "v2",
            CONF_HOST: "192.168.1.50",
            CONF_EBUS_BROKER_HOST: "span-panel.local",
            CONF_EBUS_BROKER_USERNAME: "mqtt-user",
            CONF_EBUS_BROKER_PASSWORD: "mqtt-pass",
            CONF_EBUS_BROKER_PORT: 8883,
            CONF_HTTP_PORT: 80,
        },
        entry_id="entry-no-uid",
        title="SPAN Panel",
        unique_id=None,
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.span_panel.async_register_commands"),
        pytest.raises(ConfigEntryNotReady, match="no unique_id"),
    ):
        await async_setup_entry(hass, entry)


async def test_async_setup_entry_v2_auth_error_closes_client(
    hass: HomeAssistant,
) -> None:
    """MQTT auth errors should close the client before raising."""
    entry = _create_v2_entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.connect = AsyncMock(side_effect=SpanPanelAuthError("bad auth"))
    client.close = AsyncMock()

    with (
        patch("homeassistant.components.span_panel.async_register_commands"),
        patch(
            "homeassistant.components.span_panel.SpanMqttClient", return_value=client
        ),
        pytest.raises(ConfigEntryAuthFailed, match="MQTT authentication failed"),
    ):
        await async_setup_entry(hass, entry)

    client.close.assert_awaited_once()


async def test_async_setup_entry_v1_requires_reauth(
    hass: HomeAssistant,
) -> None:
    """Legacy v1 entries should fail with a reauth request."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_VERSION: "v1", CONF_HOST: "192.168.1.50"},
        entry_id="entry-v1",
        title="SPAN Panel",
        unique_id="sp3-v1-001",
    )
    entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryAuthFailed, match="requires reauthentication"):
        await async_setup_entry(hass, entry)


async def test_async_setup_entry_unknown_api_version_raises_config_error(
    hass: HomeAssistant,
) -> None:
    """Unknown API versions should fail clearly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_VERSION: "v3", CONF_HOST: "192.168.1.50"},
        entry_id="entry-bad-api",
        title="SPAN Panel",
        unique_id="sp3-bad-api-001",
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.span_panel.async_register_commands"),
        pytest.raises(ConfigEntryError, match="Unknown api_version: v3"),
    ):
        await async_setup_entry(hass, entry)


async def test_async_setup_entry_renames_to_unique_panel_title(
    hass: HomeAssistant,
) -> None:
    """Serial-number titles should be normalized without colliding with existing entries."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_VERSION: "v2"},
        entry_id="existing-entry",
        title="SPAN Panel",
        unique_id="sp3-existing-001",
    )
    existing.add_to_hass(hass)

    entry = _create_v2_entry()
    entry.add_to_hass(hass)
    snapshot = SpanPanelSnapshotFactory.create(serial_number="sp3-setup-001")
    client = MagicMock()
    client.connect = AsyncMock()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_setup_streaming = AsyncMock()
    coordinator.data = snapshot

    with (
        patch("homeassistant.components.span_panel.async_register_commands"),
        patch(
            "homeassistant.components.span_panel.SpanMqttClient", return_value=client
        ),
        patch(
            "homeassistant.components.span_panel.SpanPanelCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.span_panel.ensure_device_registered",
            AsyncMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(hass.config_entries, "async_update_entry") as mock_update_entry,
    ):
        assert await async_setup_entry(hass, entry) is True

    assert mock_update_entry.call_args_list[-1].kwargs["title"] == "SPAN Panel 2"


async def test_async_setup_entry_shutdowns_coordinator_on_forward_failure(
    hass: HomeAssistant,
) -> None:
    """Late setup failures should shut down the coordinator."""
    entry = _create_v2_entry()
    entry.add_to_hass(hass)
    snapshot = SpanPanelSnapshotFactory.create(serial_number="sp3-setup-001")
    client = MagicMock()
    client.connect = AsyncMock()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_setup_streaming = AsyncMock()
    coordinator.async_shutdown = AsyncMock()
    coordinator.data = snapshot

    with (
        patch("homeassistant.components.span_panel.async_register_commands"),
        patch(
            "homeassistant.components.span_panel.SpanMqttClient", return_value=client
        ),
        patch(
            "homeassistant.components.span_panel.SpanPanelCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.span_panel.ensure_device_registered",
            AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("forward failed")),
        ),
        pytest.raises(RuntimeError, match="forward failed"),
    ):
        await async_setup_entry(hass, entry)

    coordinator.async_shutdown.assert_awaited_once()
