"""Tests for Paperless-ngx update platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import RemoteVersion
import pytest

from homeassistant.components.paperless_ngx.coordinator import (
    REMOTE_VERSION_UPDATE_INTERVAL_HOURS,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    MOCK_REMOTE_VERSION_DATA_LIMIT_REACHED,
    MOCK_REMOTE_VERSION_DATA_NO_UPDATE,
    MOCK_REMOTE_VERSION_DATA_UNAVAILABLE,
    MOCK_REMOTE_VERSION_DATA_UPDATE,
)

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("init_integration")
async def test_update_sensor_state(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure update entities are added automatically."""
    # initialize with no new update
    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_OFF

    # update available
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=MOCK_REMOTE_VERSION_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_ON

    # no new update available
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=MOCK_REMOTE_VERSION_DATA_NO_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_OFF

    # paperless return none -> unavailable
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=MOCK_REMOTE_VERSION_DATA_UNAVAILABLE, fetched=True
        )
    )

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE

    # fetch no new update within fetching limit stays unavailable
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=MOCK_REMOTE_VERSION_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE

    # return back available
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=MOCK_REMOTE_VERSION_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_ON

    # fetch github api limit reached
    mock_paperless.remote_version = AsyncMock(
        return_value=RemoteVersion.create_with_data(
            mock_paperless, data=MOCK_REMOTE_VERSION_DATA_LIMIT_REACHED, fetched=True
        )
    )

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("init_integration")
async def test_update_sensor_state_on_error(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure update entities are added automatically."""
    # initialize with no new update
    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_OFF

    # PaperlessConnectionError
    mock_paperless.remote_version.side_effect = PaperlessConnectionError

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessConnectionError
    mock_paperless.remote_version.side_effect = None

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_OFF

    # PaperlessInvalidAuthError
    mock_paperless.remote_version.side_effect = PaperlessInvalidTokenError

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessInvalidTokenError
    mock_paperless.remote_version.side_effect = None

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_OFF

    # PaperlessInactiveOrDeletedError
    mock_paperless.remote_version.side_effect = PaperlessInactiveOrDeletedError

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessInactiveOrDeletedError
    mock_paperless.remote_version.side_effect = None

    freezer.tick(timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.paperless_ngx_firmware")
    assert state.state == STATE_OFF
