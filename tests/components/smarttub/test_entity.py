"""Test SmartTubEntity."""

from homeassistant.components.smarttub.entity import SmartTubEntity


async def test_entity(coordinator, spa):
    """Test SmartTubEntity."""

    entity = SmartTubEntity(coordinator, spa, "entity1")

    assert entity.device_info
    assert entity.name

    coordinator.data[spa.id] = {}
    assert entity.get_spa_status("foo") is None
    coordinator.data[spa.id]["status"] = {"foo": "foo1", "bar": {"baz": "barbaz1"}}
    assert entity.get_spa_status("foo") == "foo1"
    assert entity.get_spa_status("bar.baz") == "barbaz1"
