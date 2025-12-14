"""Tests for Paperless-ngx sensor platform."""

from freezegun.api import FrozenDateTimeFactory
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import Statistic
import pytest

from homeassistant.components.paperless_ngx.coordinator import (
    UPDATE_INTERVAL_STATISTICS,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test paperless_ngx update sensors."""
    with patch("homeassistant.components.paperless_ngx.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_statistic_sensor_state(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_statistic_data_update,
) -> None:
    """Ensure sensor entities are added automatically."""
    # initialize with 999 documents
    state = hass.states.get("sensor.paperless_ngx_total_documents")
    assert state.state == "999"

    # update to 420 documents
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=mock_statistic_data_update, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_STATISTICS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_total_documents")
    assert state.state == "420"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("error_cls", "assert_state"),
    [
        (PaperlessForbiddenError, "420"),
        (PaperlessConnectionError, "420"),
        (PaperlessInactiveOrDeletedError, STATE_UNAVAILABLE),
        (PaperlessInvalidTokenError, STATE_UNAVAILABLE),
    ],
)
async def test__statistic_sensor_state_on_error(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_statistic_data_update,
    error_cls,
    assert_state,
) -> None:
    """Ensure sensor entities are added automatically."""
    # simulate error
    mock_paperless.statistics.side_effect = error_cls

    freezer.tick(UPDATE_INTERVAL_STATISTICS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_total_documents")
    assert state.state == STATE_UNAVAILABLE

    # recover from not auth errors
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=mock_statistic_data_update, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_STATISTICS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_total_documents")
    assert state.state == assert_state
