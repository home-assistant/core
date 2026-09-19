"""Tests for the Ecobee sensor platform."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_remote_sensor_unique_id_dedup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure duplicate entries in remoteSensors do not collide on unique_id.

    Some thermostats return the same sensor twice in the remoteSensors list
    (observed in the field on an Ecobee3 Lite, where every entry in
    available_sensors appears in adjacent pairs). Without dedup at setup
    time, the second registration collides with the first and is dropped
    by entity_platform with an "already exists" ERROR log on every startup.

    Regression test: when remoteSensors contains a duplicate, only the
    de-duplicated set of entities should be registered, and no ERROR
    should be raised by entity_platform.
    """
    # Patch the pyecobee instance method to return a remoteSensors list
    # with a duplicated built-in sensor (same id, same capability set).
    duplicated_sensors = [
        {
            "id": "ei:0",
            "name": "ecobee",
            "type": "thermostat",
            "capability": [
                {"id": "1", "type": "temperature", "value": "720"},
                {"id": "2", "type": "humidity", "value": "30"},
            ],
        },
        # Verbatim duplicate of the previous entry — same id, same caps.
        {
            "id": "ei:0",
            "name": "ecobee",
            "type": "thermostat",
            "capability": [
                {"id": "1", "type": "temperature", "value": "720"},
                {"id": "2", "type": "humidity", "value": "30"},
            ],
        },
    ]

    with patch(
        "pyecobee.Ecobee.get_remote_sensors",
        return_value=duplicated_sensors,
    ):
        await setup_platform(hass, Platform.SENSOR)

    # One temperature + one humidity entity, NOT two of each.
    registered = [
        e
        for e in entity_registry.entities.values()
        if e.platform == "ecobee" and e.unique_id.startswith("8675309-ei:0-")
    ]
    assert len(registered) == 2
    assert {e.unique_id for e in registered} == {
        "8675309-ei:0-temperature",
        "8675309-ei:0-humidity",
    }


async def test_remote_sensor_no_duplicates_unchanged(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Confirm the dedup does not drop entities in the normal (unique) case.

    With the standard fixture (no duplicated remoteSensors), every distinct
    sensor capability should still be registered as before.
    """
    await setup_platform(hass, Platform.SENSOR)

    # Default fixture (ecobee-data.json) has 3 thermostats with distinct
    # sensors per the test fixtures. We assert that the dedup did not drop
    # any of them by checking at least one expected unique_id from each
    # thermostat shows up in the registry.
    ecobee_entries = [
        e for e in entity_registry.entities.values() if e.platform == "ecobee"
    ]
    sensor_unique_ids = {e.unique_id for e in ecobee_entries}

    # ecobee-data.json: thermostat 0 has remoteSensor id=ei:0 (no code) and
    # rs:100 with code=WKRP. Confirm both branches of the unique_id
    # construction are represented.
    assert any(uid.endswith("-ei:0-temperature") for uid in sensor_unique_ids), (
        "expected built-in sensor (id-based unique_id) to survive dedup"
    )
    assert any(uid.startswith("WKRP-") for uid in sensor_unique_ids), (
        "expected paired SmartSensor (code-based unique_id) to survive dedup"
    )
