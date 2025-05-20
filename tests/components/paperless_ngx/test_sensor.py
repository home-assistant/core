"""Tests for Paperless-ngx sensor platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import Statistic
import pytest

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import MOCK_STATISTICS_DATA_UPDATE

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_platfom(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test paperless_ngx update sensors."""
    with patch("homeassistant.components.paperless_ngx.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("init_integration")
async def test_statistic_sensor_state(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure sensor entities are added automatically."""
    # initialize with 999 documents
    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == "999"

    # update to 420 documents
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=MOCK_STATISTICS_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == "420"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("init_integration")
async def test__statistic_sensor_state_on_error(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure sensor entities are added automatically."""
    # PaperlessForbiddenError
    mock_paperless.statistics.side_effect = PaperlessForbiddenError

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessForbiddenError
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=MOCK_STATISTICS_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == "420"

    # PaperlessConnectionError
    mock_paperless.statistics.side_effect = PaperlessConnectionError

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessConnectionError
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=MOCK_STATISTICS_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == "420"

    # PaperlessInactiveOrDeletedError
    mock_paperless.statistics.side_effect = PaperlessInactiveOrDeletedError

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessInactiveOrDeletedError
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=MOCK_STATISTICS_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == "420"

    # PaperlessInvalidTokenError
    mock_paperless.statistics.side_effect = PaperlessInvalidTokenError

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == STATE_UNAVAILABLE

    # recover from PaperlessInvalidTokenError
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=MOCK_STATISTICS_DATA_UPDATE, fetched=True
        )
    )

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.paperless_ngx_documents_total")
    assert state.state == "420"
