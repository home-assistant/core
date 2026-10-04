"""Test the services of the ENGIE Belgium integration."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from aioengiebelgium import EngieBeCommunicationError
import pytest

from homeassistant.components.engie_be.const import (
    DOMAIN,
    SERVICE_GET_EPEX_PRICES_FOR_DATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import build_epex_payload_without_tomorrow, setup_entry

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_engie_client")


async def _call_service(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Call the get EPEX prices service and return its response."""
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_EPEX_PRICES_FOR_DATE,
        dict(data),
        blocking=True,
        return_response=True,
    )


async def test_get_epex_prices_for_date(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    frozen_afternoon: None,
) -> None:
    """Test the service returns the hourly slots of the requested date."""
    await setup_entry(hass, mock_config_entry)

    response = await _call_service(
        hass, {"config_entry": mock_config_entry.entry_id, "date": "2026-10-03"}
    )
    slots = response["slots"]
    assert len(slots) == 24
    assert slots[0] == {
        "start": datetime(2026, 10, 2, 22, 0, tzinfo=UTC).isoformat(),
        "end": datetime(2026, 10, 2, 23, 0, tzinfo=UTC).isoformat(),
        "value": 0.01,
    }
    assert slots[-1]["value"] == pytest.approx(0.24)


async def test_get_epex_prices_for_date_quarter_hourly(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    frozen_afternoon: None,
) -> None:
    """Test the service returns quarter-hourly slots for the requested granularity."""
    await setup_entry(hass, mock_config_entry)

    response = await _call_service(
        hass,
        {
            "config_entry": mock_config_entry.entry_id,
            "date": "2026-10-03",
            "granularity": "quarter_hourly",
        },
    )
    slots = response["slots"]
    assert len(slots) == 96
    assert slots[0]["value"] == pytest.approx(0.01)
    assert slots[1]["value"] == pytest.approx(0.0125)
    assert slots[-1]["value"] == pytest.approx(0.2475)


async def test_get_epex_prices_for_date_rejects_other_dates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    frozen_afternoon: None,
) -> None:
    """Test the service rejects any date other than today and tomorrow."""
    await setup_entry(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="Only today and tomorrow"):
        await _call_service(
            hass, {"config_entry": mock_config_entry.entry_id, "date": "2026-10-02"}
        )


async def test_get_epex_prices_for_date_not_published(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
) -> None:
    """Test the service reports a validation error for unpublished prices."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_without_tomorrow
    )
    await setup_entry(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="not published yet"):
        await _call_service(
            hass, {"config_entry": mock_config_entry.entry_id, "date": "2026-10-04"}
        )


async def test_get_epex_prices_for_date_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
) -> None:
    """Test the service reports a HomeAssistantError when the API is unreachable."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    await setup_entry(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="connection error") as exc_info:
        await _call_service(
            hass, {"config_entry": mock_config_entry.entry_id, "date": "2026-10-03"}
        )
    assert type(exc_info.value) is HomeAssistantError


async def test_get_epex_prices_for_date_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    frozen_afternoon: None,
) -> None:
    """Test the service rejects a config entry that is not loaded."""
    await setup_entry(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_service(
            hass, {"config_entry": mock_config_entry.entry_id, "date": "2026-10-03"}
        )
    assert exc_info.value.translation_key == "service_config_entry_not_loaded"


async def test_get_epex_prices_for_date_unknown_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    frozen_afternoon: None,
) -> None:
    """Test the service rejects a config entry that does not exist."""
    await setup_entry(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_service(hass, {"config_entry": "unknown", "date": "2026-10-03"})
    assert exc_info.value.translation_key == "service_config_entry_not_found"
