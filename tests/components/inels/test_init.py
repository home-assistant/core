"""Tests for iNELS integration."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.core import HomeAssistant

from . import HA_INELS_PATH
from .common import DOMAIN, inels
from .test_config_flow import default_config  # noqa: F401

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("error_code", "expected_exception", "expected_result"),
    [
        (4, ConfigEntryAuthFailed, None),
        (3, ConfigEntryNotReady, None),
        (6, None, False),
    ],
)
async def test_connection(
    hass: HomeAssistant,
    error_code,
    expected_exception,
    expected_result,
    default_config,  # noqa: F811
) -> None:
    """Test async_setup_entry with various connection scenarios."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config)
    config_entry.add_to_hass(hass)

    with patch(f"{HA_INELS_PATH}.InelsMqtt.test_connection", return_value=error_code):
        if expected_exception:
            with pytest.raises(expected_exception):
                await inels.async_setup_entry(hass, config_entry)
        else:
            result = await inels.async_setup_entry(hass, config_entry)
            assert result is expected_result
