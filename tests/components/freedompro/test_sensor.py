"""Tests for the Freedompro sensor."""
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "entity_id, device_class, state",
    [
        ("sensor.garden_humidity_sensor", "humidity", 0),
        ("sensor.temperatureSensor", "temperature", 0),
    ]
)
async def test_sensor_get_state(hass, init_integration):
    ...
    """Test states of the sensor."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "sensor.garden_humidity_sensor"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == "Garden humidity sensor"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*QN-DDFMPEPRDOQV7W7JQG3NL0NPZGTLIBYT3HFSPNEY"
    )
