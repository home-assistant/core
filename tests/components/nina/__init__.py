"""Tests for the Nina integration."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

from pynina import Warning

from homeassistant.components.nina.const import CONF_REGIONS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


async def setup_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Set up the NINA platform."""
    mock_nina_class.warnings = {
        region: deepcopy(nina_warnings)
        for region in config_entry.data.get(CONF_REGIONS, {})
    }

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


def mocked_request_function(url: str) -> dict[str, Any]:
    """Mock of the request function."""
    dummy_response: list[dict[str, Any]] = load_json_array_fixture(
        "sample_warnings.json", DOMAIN
    )

    dummy_response_details: dict[str, Any] = load_json_object_fixture(
        "sample_warning_details.json", DOMAIN
    )

    dummy_response_regions: dict[str, Any] = load_json_object_fixture(
        "sample_regions.json", DOMAIN
    )

    dummy_response_labels: dict[str, Any] = load_json_object_fixture(
        "sample_labels.json", DOMAIN
    )

    if "https://warnung.bund.de/api31/dashboard/" in url:  # codespell:ignore bund
        return dummy_response

    if (
        "https://warnung.bund.de/api/appdata/gsb/labels/de_labels.json"  # codespell:ignore bund
        in url
    ):
        return dummy_response_labels

    if (
        url
        == "https://www.xrepository.de/api/xrepository/urn:de:bund:destatis:bevoelkerungsstatistik:schluessel:rs_2021-07-31/download/Regionalschl_ssel_2021-07-31.json"  # codespell:ignore bund
    ):
        return dummy_response_regions

    warning_id = url.replace(
        "https://warnung.bund.de/api31/warnings/",  # codespell:ignore bund
        "",
    ).replace(".json", "")

    return dummy_response_details[warning_id]
