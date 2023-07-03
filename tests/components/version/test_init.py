"""The tests for version init."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.version.const import (
    CONF_BOARD,
    CONF_IMAGE,
    DEFAULT_CONFIGURATION,
)
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant

from .common import (
    MOCK_VERSION,
    MOCK_VERSION_CONFIG_ENTRY_DATA,
    MOCK_VERSION_DATA,
)

from tests.common import MockConfigEntry


async def test_unsupported_board(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test configuring with an unsupported board."""
    mock_entry = MockConfigEntry(
        **{
            **MOCK_VERSION_CONFIG_ENTRY_DATA,
            "data": {
                **DEFAULT_CONFIGURATION,
                CONF_BOARD: "not-supported",
            },
        }
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "pyhaversion.HaVersion.get_version",
        return_value=(MOCK_VERSION, MOCK_VERSION_DATA),
    ):
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            'Board "not-supported" is (no longer) valid. Please remove the integration "Local installation"'
            in caplog.text
        )


async def test_unsupported_container_image(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test configuring with an unsupported container image."""
    mock_entry = MockConfigEntry(
        **{
            **MOCK_VERSION_CONFIG_ENTRY_DATA,
            "data": {
                **DEFAULT_CONFIGURATION,
                CONF_IMAGE: "not-supported-homeassistant",
                CONF_SOURCE: "container",
            },
        }
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "pyhaversion.HaVersion.get_version",
        return_value=(MOCK_VERSION, MOCK_VERSION_DATA),
    ):
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            'Image "not-supported-homeassistant" is (no longer) valid. Please remove the integration "Local installation"'
            in caplog.text
        )
