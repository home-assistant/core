"""Test the influxdb config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.influxdb import DOMAIN
from homeassistant.core import HomeAssistant

from . import BASE_V1_CONFIG, BASE_V2_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "config_base",
    [
        BASE_V1_CONFIG,
        BASE_V2_CONFIG,
    ],
)
async def test_import(hass: HomeAssistant, config_base) -> None:
    """Test we can import."""
    with patch(
        "homeassistant.components.influxdb.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config_base,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == config_base["host"]
    assert result["data"] == config_base


@pytest.mark.parametrize(
    "config_base",
    [
        BASE_V1_CONFIG,
        BASE_V2_CONFIG,
    ],
)
async def test_import_update(hass: HomeAssistant, config_base) -> None:
    """Test we can import and update the config."""
    config_ext = {
        "include": {
            "entities": ["another_fake.included", "fake.excluded_pass"],
            "entity_globs": [],
            "domains": [],
        },
        "exclude": {
            "domains": ["another_fake"],
            "entity_globs": ["*.excluded_*"],
            "entities": [],
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_base,
        unique_id=config_base["host"],
    )
    entry.add_to_hass(hass)

    config = config_base.copy()
    config.update(config_ext)

    with patch(
        "homeassistant.components.influxdb.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data == config
