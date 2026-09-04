"""Test OpenAQ data coordinator helpers."""

from types import MappingProxyType
from typing import cast
from unittest.mock import MagicMock, patch

from openaq import NotAuthorizedError, OpenAQ, ServerError
import pytest

from homeassistant.components.openaq.const import CONF_LOCATION_ID, DOMAIN
from homeassistant.components.openaq.coordinator import (
    OpenAQDataUpdateCoordinator,
    _build_sensor_metadata,
    async_create_openaq_client,
    create_openaq_client,
    normalize_latest_measurements,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, UnitOfDensity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import API_KEY, LOCATION_ID, make_latest, make_sensor

from tests.common import MockConfigEntry


def test_create_openaq_client_uses_sync_openaq_client() -> None:
    """Test creating an OpenAQ client uses the sync SDK client."""
    api_key = "a" * 64
    client = create_openaq_client(api_key)

    try:
        assert isinstance(client, OpenAQ)
        assert client.api_key == api_key
    finally:
        client.close()


async def test_async_create_openaq_client_uses_executor(
    hass: HomeAssistant,
) -> None:
    """Test creating an OpenAQ client through Home Assistant."""
    mock_client = MagicMock()

    with patch(
        "homeassistant.components.openaq.coordinator.create_openaq_client",
        return_value=mock_client,
    ) as mock_create:
        client = await async_create_openaq_client(hass, "api-key")

    assert client is mock_client
    mock_create.assert_called_once_with("api-key")


async def test_initial_refresh_sdk_error_raises_update_failed(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
) -> None:
    """Test initial refresh SDK errors raise UpdateFailed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Del Norte",
                unique_id=str(LOCATION_ID),
            )
        ],
    )
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        config_entry,
        next(iter(config_entry.subentries.values())),
        mock_openaq_client,
    )
    api_error = ServerError("API error")
    mock_openaq_client.locations.get.side_effect = api_error

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is api_error
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "unable_to_fetch"


async def test_initial_refresh_auth_error_raises_update_failed(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
) -> None:
    """Test initial refresh auth errors raise UpdateFailed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Del Norte",
                unique_id=str(LOCATION_ID),
            )
        ],
    )
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        config_entry,
        next(iter(config_entry.subentries.values())),
        mock_openaq_client,
    )
    auth_error = NotAuthorizedError("Invalid API key")
    mock_openaq_client.locations.get.side_effect = auth_error

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is auth_error
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "unable_to_fetch"


async def test_initial_refresh_runs_sdk_calls_in_executor(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test blocking SDK calls run in the executor."""
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        mock_openaq_client,
    )

    with patch.object(
        hass, "async_add_executor_job", wraps=hass.async_add_executor_job
    ) as mock_executor:
        await coordinator._async_update_data()

    assert mock_executor.call_count == 1


def test_normalize_latest_measurements() -> None:
    """Test normalizing latest measurements by sensor metadata."""
    by_id, _ = _build_sensor_metadata(
        [
            make_sensor(1, "pm2.5", "µg/m3"),
            make_sensor(2, "pm10"),
        ],
    )
    measurements = normalize_latest_measurements(
        [
            make_latest(1, 8.5),
            make_latest(999, 44.1),
            make_latest(2, None),
        ],
        by_id,
    )

    assert measurements == MappingProxyType({"pm25": 8.5})


def test_build_sensor_metadata() -> None:
    """Test normalizing sensor metadata by parameter."""
    _, units = _build_sensor_metadata(
        [
            make_sensor(1, "pm2.5", "µg/m3"),
            make_sensor(2, "pm10"),
        ]
    )

    assert units == MappingProxyType(
        {
            "pm25": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
            "pm10": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        }
    )


@pytest.mark.parametrize(
    ("unit", "expected_unit"),
    [
        ("μg/m³", UnitOfDensity.MICROGRAMS_PER_CUBIC_METER),
        ("mg/m³", UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER),
        ("mg/m3", UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER),
    ],
)
def test_normalize_latest_measurements_normalizes_unit_aliases(
    unit: str, expected_unit: str
) -> None:
    """Test normalizing measurement unit aliases."""
    by_id, units = _build_sensor_metadata([make_sensor(1, "pm10", unit)])
    measurements = normalize_latest_measurements(
        [make_latest(1, 12.1)],
        by_id,
    )

    assert measurements == MappingProxyType({"pm10": 12.1})
    assert units == MappingProxyType({"pm10": expected_unit})


def test_normalize_latest_measurements_allows_missing_units() -> None:
    """Test normalizing a measurement without a reported unit."""
    by_id, units = _build_sensor_metadata(
        [make_sensor(1, "pm10", cast(str, None))],
    )
    measurements = normalize_latest_measurements(
        [make_latest(1, 12.1)],
        by_id,
    )

    assert measurements == MappingProxyType({"pm10": 12.1})
    assert units == MappingProxyType({"pm10": None})


async def test_update_data_auth_error_raises_update_failed(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refresh auth errors raise UpdateFailed."""
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        mock_openaq_client,
    )
    await coordinator._async_update_data()
    mock_openaq_client.locations.latest.side_effect = NotAuthorizedError(
        "Invalid API key"
    )

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "unable_to_fetch"
