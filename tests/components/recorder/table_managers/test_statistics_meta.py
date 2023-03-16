"""The tests for the Recorder component."""
from __future__ import annotations

import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant

from tests.typing import RecorderInstanceGenerator


async def test_passing_mutually_exclusive_options_to_get_many(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we expire after many commits."""
    instance = await async_setup_recorder_instance(
        hass, {recorder.CONF_COMMIT_INTERVAL: 0}
    )
    with session_scope(session=instance.get_session()) as session:
        with pytest.raises(ValueError):
            instance.statistics_meta_manager.get_many(
                session,
                statistic_ids=["light.kitchen"],
                statistic_type="mean",
            )
        with pytest.raises(ValueError):
            instance.statistics_meta_manager.get_many(
                session, statistic_ids=["light.kitchen"], statistic_source="sensor"
            )
        assert (
            instance.statistics_meta_manager.get_many(
                session,
                statistic_ids=["light.kitchen"],
            )
            == {}
        )
