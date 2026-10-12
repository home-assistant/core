"""Verify discovery never probes ignored or already configured hosts."""

from dataclasses import replace
import json
import logging
from unittest.mock import AsyncMock

from linkplay.manufacturers import MANUFACTURER_WIIM
import pytest

from homeassistant.components.linkplay.const import DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, NAME
from .test_config_flow import ZEROCONF_DISCOVERY

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("source", "properties", "expected_probes", "expected_reason"),
    [
        pytest.param(
            SOURCE_IGNORE,
            {"uuid": "uuid:FF31F09E-5001-FBDE-0546-2DBF"},
            0,
            "already_configured",
            id="ignored_matching_uuid_no_probe",
        ),
        pytest.param(
            SOURCE_IGNORE,
            ZEROCONF_DISCOVERY.properties,
            0,
            "already_configured",
            id="ignored_extra_suffix_uuid_no_probe",
        ),
        pytest.param(
            SOURCE_USER,
            ZEROCONF_DISCOVERY.properties,
            0,
            "already_configured",
            id="configured_extra_suffix_uuid_no_probe",
        ),
        pytest.param(
            SOURCE_IGNORE,
            {},
            0,
            "already_configured",
            id="ignored_missing_uuid_no_probe",
        ),
    ],
)
async def test_uuid_causality(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
    source: str,
    properties: dict[str, str],
    expected_probes: int,
    expected_reason: str,
) -> None:
    """Isolate UUID matching and ignore status with a WiiM API response."""
    api_uuid = "FF31F09E5001FBDE05462DBF"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_HOST: HOST},
        source=source,
        unique_id=api_uuid,
    )
    entry.add_to_hass(hass)
    mock_linkplay_factory_bridge.return_value.device.uuid = api_uuid
    mock_linkplay_factory_bridge.return_value.device.manufacturer = MANUFACTURER_WIIM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(ZEROCONF_DISCOVERY, properties=properties),
    )

    _LOGGER.info(
        "%s",
        json.dumps(
            {
                "source": source,
                "advertised_uuid": properties.get("uuid"),
                "saved_and_api_uuid": api_uuid,
                "api_factory_calls": mock_linkplay_factory_bridge.call_count,
                "api_factory_awaits": mock_linkplay_factory_bridge.await_count,
                "abort_reason": result["reason"],
            }
        ),
    )
    assert mock_linkplay_factory_bridge.call_count == expected_probes
    assert mock_linkplay_factory_bridge.await_count == expected_probes
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize("source", [SOURCE_IGNORE, SOURCE_USER])
@pytest.mark.parametrize(
    ("other_entry_data", "expected_probes", "expected_reason"),
    [
        pytest.param({}, 1, "not_linkplay_device", id="current_entry_excluded"),
        pytest.param(
            {CONF_HOST: HOST},
            0,
            "already_configured",
            id="other_matching_entry_still_blocks",
        ),
    ],
)
async def test_host_guard_excludes_current_entry_only(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
    source: str,
    other_entry_data: dict[str, str],
    expected_probes: int,
    expected_reason: str,
) -> None:
    """Exclude the current entry, but continue checking other saved entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_HOST: HOST},
        source=source,
        unique_id="FF31F09E5001FBDE05462DBF",
    )
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other ignored device",
        data=other_entry_data,
        source=SOURCE_IGNORE,
        unique_id="0123456789ABCDEF01234567",
    )
    other_entry.add_to_hass(hass)
    mock_linkplay_factory_bridge.return_value.device.manufacturer = MANUFACTURER_WIIM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF, "entry_id": entry.entry_id},
        data=ZEROCONF_DISCOVERY,
    )

    _LOGGER.info(
        "Current entry source=%s; other entry data=%s; API awaits=%s; reason=%s",
        source,
        other_entry_data,
        mock_linkplay_factory_bridge.await_count,
        result["reason"],
    )
    assert mock_linkplay_factory_bridge.call_count == expected_probes
    assert mock_linkplay_factory_bridge.await_count == expected_probes
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
