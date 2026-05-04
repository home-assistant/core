"""Test OpenAQ data coordinator helpers."""

from types import MappingProxyType, SimpleNamespace

from homeassistant.components.openaq.coordinator import (
    OpenAQMeasurement,
    create_openaq_client,
    get_openaq_value,
    normalize_latest_measurements,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)

from .conftest import make_latest, make_sensor


async def test_create_openaq_client_uses_fresh_transport() -> None:
    """Test OpenAQ clients do not share a closable transport."""
    client = create_openaq_client("api-key")
    other_client = create_openaq_client("api-key")

    try:
        assert client.transport is not other_client.transport
        await client.close()
        assert not other_client.transport.client.is_closed
    finally:
        await other_client.close()


def test_get_openaq_value_dict() -> None:
    """Test getting OpenAQ values from dict data."""
    data = {"id": 123}

    assert get_openaq_value(data, "id") == 123
    assert get_openaq_value(data, "missing") is None


def test_normalize_latest_measurements_ignores_invalid_data() -> None:
    """Test normalizing latest measurements ignores invalid API data."""
    measurements = normalize_latest_measurements(
        [
            make_latest("1", 8.5),
            make_latest("unknown", 12.1),
            make_latest(2, True),
            make_latest(3, 33.2),
        ],
        [
            make_sensor("1", "pm2.5", "µg/m3"),
            make_sensor(2, "pm10"),
            make_sensor(3, "no_units", 123),
            SimpleNamespace(id=4, parameter=SimpleNamespace()),
        ],
    )

    assert measurements == MappingProxyType(
        {
            "pm25": OpenAQMeasurement(
                parameter="pm25",
                value=8.5,
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            ),
            "nounits": OpenAQMeasurement(
                parameter="nounits",
                value=33.2,
                unit=None,
            ),
        }
    )


def test_normalize_latest_measurements_uses_sensor_latest() -> None:
    """Test normalizing measurements from sensor latest data."""
    measurements = normalize_latest_measurements(
        [],
        [make_sensor(1, "pm10", "mg/m3", value=12.1)],
    )

    assert measurements == MappingProxyType(
        {
            "pm10": OpenAQMeasurement(
                parameter="pm10",
                value=12.1,
                unit=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
            )
        }
    )
