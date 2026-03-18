"""Tests for the Risco integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.risco.const import (
    CONF_COMMUNICATION_DELAY,
    DOMAIN,
    TYPE_LOCAL,
)
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_error_handler():
    """Create a mock for add_error_handler."""
    with patch("homeassistant.components.risco.RiscoLocal.add_error_handler") as mock:
        yield mock


async def test_connection_reset(
    hass: HomeAssistant, two_zone_local, mock_error_handler, setup_risco_local
) -> None:
    """Test config entry reload on connection reset."""

    callback = mock_error_handler.call_args.args[0]
    assert callback is not None

    with patch.object(hass.config_entries, "async_reload") as reload_mock:
        await callback(Exception())
        reload_mock.assert_not_awaited()

        await callback(ConnectionResetError())
        reload_mock.assert_awaited_once()


async def test_unload_handles_disconnect_error(
    hass: HomeAssistant, two_zone_local, setup_risco_local
) -> None:
    """Test unload succeeds when local disconnect errors out."""
    with patch(
        "homeassistant.components.risco.RiscoLocal.disconnect",
        side_effect=RuntimeError("disconnect failed"),
    ) as disconnect_mock:
        assert await hass.config_entries.async_unload(setup_risco_local.entry_id)
        disconnect_mock.assert_awaited_once()


async def test_local_setup_uses_stored_communication_delay(
    hass: HomeAssistant,
) -> None:
    """Test local setup passes stored communication delay to the client."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: TYPE_LOCAL,
            CONF_HOST: "test-host",
            CONF_PORT: 5004,
            CONF_PIN: "1234",
            CONF_COMMUNICATION_DELAY: 2,
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.risco.RiscoLocal", autospec=True
        ) as risco_local,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        risco_local.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        risco_local.assert_called_once_with(
            "test-host",
            5004,
            "1234",
            communication_delay=2,
            concurrency=4,
        )
