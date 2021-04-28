"""Common test tools."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Awaitable, Callable, cast

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import async_recorder_block_till_done

from tests.common import (
    async_init_recorder_component,
    get_test_home_assistant,
    init_recorder_component,
)

SetupRecorderInstanceT = Callable[..., Awaitable[Recorder]]


@pytest.fixture
def hass_recorder():
    """Home Assistant fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Set up with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


@pytest.fixture
async def async_setup_recorder_instance() -> AsyncGenerator[
    SetupRecorderInstanceT, None
]:
    """Yield callable to setup recorder instance."""

    async def async_setup_recorder(
        hass: HomeAssistantType, config: ConfigType | None = None
    ) -> Recorder:
        """Setup and return recorder instance."""  # noqa: D401
        await async_init_recorder_component(hass, config)
        await hass.async_block_till_done()
        instance = cast(Recorder, hass.data[DATA_INSTANCE])
        await async_recorder_block_till_done(hass, instance)
        assert isinstance(instance, Recorder)
        return instance

    yield async_setup_recorder
