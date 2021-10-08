"""Common test tools."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Awaitable, Callable, cast
from unittest.mock import patch

import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .common import async_recorder_block_till_done

from tests.common import async_init_recorder_component

SetupRecorderInstanceT = Callable[..., Awaitable[Recorder]]


@pytest.fixture
async def async_setup_recorder_instance(
    enable_statistics,
) -> AsyncGenerator[SetupRecorderInstanceT, None]:
    """Yield callable to setup recorder instance."""

    async def async_setup_recorder(
        hass: HomeAssistant, config: ConfigType | None = None
    ) -> Recorder:
        """Setup and return recorder instance."""  # noqa: D401
        stats = (
            recorder.Recorder.async_periodic_statistics if enable_statistics else None
        )
        with patch(
            "homeassistant.components.recorder.Recorder.async_periodic_statistics",
            side_effect=stats,
            autospec=True,
        ):
            await async_init_recorder_component(hass, config)
            await hass.async_block_till_done()
            instance = cast(Recorder, hass.data[DATA_INSTANCE])
            await async_recorder_block_till_done(hass, instance)
            assert isinstance(instance, Recorder)
            return instance

    yield async_setup_recorder
