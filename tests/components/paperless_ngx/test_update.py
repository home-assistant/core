"""Tests for Paperless-ngx update platform."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import RemoteVersion
import pytest

from homeassistant.components.paperless_ngx.coordinator import (
    UPDATE_INTERVAL_REMOTE_VERSION,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_platfom(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test paperless_ngx update sensors."""
    with patch("homeassistant.components.paperless_ngx.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("error_cls", "assert_state"),
    [
        (PaperlessConnectionError, STATE_ON),
        (PaperlessForbiddenError, STATE_ON),
        (PaperlessInactiveOrDeletedError, STATE_UNAVAILABLE),
        (PaperlessInvalidTokenError, STATE_UNAVAILABLE),
    ],
)
async def test__update_sensor_state_on_error(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_remote_version_data: MagicMock,
    error_cls,
    assert_state,
) -> None:
    """Ensure update entities are added automatically."""
    # simulate error
    mock_paperless.remote_version.side_effect = error_cls

    freezer.tick(UPDATE_INTERVAL_REMOTE_VERSION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE

    # recover from not auth errors
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=mock_remote_version_data, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_REMOTE_VERSION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == assert_state


@pytest.mark.usefixtures("init_integration")
async def test__update_sensor_version_unavailable(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_remote_version_data_unavailable: MagicMock,
) -> None:
    """Ensure update entities are added automatically."""

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_ON

    # set version unavailable
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=mock_remote_version_data_unavailable, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_REMOTE_VERSION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE
