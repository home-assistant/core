"""Test zone component."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant import setup
from homeassistant.components import device_tracker, zone
from homeassistant.components.zone import ATTR_RADIUS, DOMAIN, _zone_relation
from homeassistant.components.zone.const import ZoneEntityStateAttribute, ZoneRelation
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            "id": "from_storage",
                            "name": "from storage",
                            "latitude": 1,
                            "longitude": 2,
                            "radius": 3,
                            "passive": False,
                            "icon": "mdi:from-storage",
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": items},
            }
        if config is None:
            config = {}
        return await setup.async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_setup_no_zones_still_adds_home_zone(hass: HomeAssistant) -> None:
    """Test if no config is passed in we still get the home zone."""
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": None})
    assert len(hass.states.async_entity_ids(DOMAIN)) == 1
    state = hass.states.get("zone.home")
    assert hass.config.location_name == state.name
    assert hass.config.latitude == state.attributes["latitude"]
    assert hass.config.longitude == state.attributes["longitude"]
    assert not state.attributes.get("passive", False)


async def test_setup(hass: HomeAssistant) -> None:
    """Test a successful setup."""
    info = {
        "name": "Test Zone",
        "latitude": 32.880837,
        "longitude": -117.237561,
        "radius": 250,
        "passive": True,
    }
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})

    assert len(hass.states.async_entity_ids(DOMAIN)) == 2
    state = hass.states.get("zone.test_zone")
    assert info["name"] == state.name
    assert info["latitude"] == state.attributes["latitude"]
    assert info["longitude"] == state.attributes["longitude"]
    assert info["radius"] == state.attributes["radius"]
    assert info["passive"] == state.attributes["passive"]


async def test_setup_zone_skips_home_zone(hass: HomeAssistant) -> None:
    """Test that zone named Home should override hass home zone."""
    info = {"name": "Home", "latitude": 1.1, "longitude": -2.2}
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})

    assert len(hass.states.async_entity_ids(DOMAIN)) == 1
    state = hass.states.get("zone.home")
    assert info["name"] == state.name


async def test_setup_name_can_be_same_on_multiple_zones(hass: HomeAssistant) -> None:
    """Test that zone named Home should override hass home zone."""
    info = {"name": "Test Zone", "latitude": 1.1, "longitude": -2.2}
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": [info, info]})
    assert len(hass.states.async_entity_ids(DOMAIN)) == 3


@pytest.mark.usefixtures("improved_presence_detection")
async def test_active_zone_skips_passive_zones(hass: HomeAssistant) -> None:
    """Test active and passive zones."""
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Passive Zone",
                    "latitude": 32.880600,
                    "longitude": -117.237561,
                    "radius": 250,
                    "passive": True,
                }
            ]
        },
    )
    await hass.async_block_till_done()
    active_zone = zone.async_active_zone(hass, 32.880600, -117.237561)
    assert active_zone is None
    active_zone, in_zones = zone.async_in_zones(hass, 32.880600, -117.237561)
    assert active_zone is None
    assert in_zones == ["zone.passive_zone"]


@pytest.mark.usefixtures("improved_presence_detection")
async def test_active_zone_skips_passive_zones_2(hass: HomeAssistant) -> None:
    """Test active and passive zones."""
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Active Zone",
                    "latitude": 32.880800,
                    "longitude": -117.237561,
                    "radius": 500,
                }
            ]
        },
    )
    await hass.async_block_till_done()
    active_zone = zone.async_active_zone(hass, 32.880700, -117.237561)
    assert active_zone.entity_id == "zone.active_zone"
    active_zone, in_zones = zone.async_in_zones(hass, 32.880600, -117.237561)
    assert active_zone.entity_id == "zone.active_zone"
    assert in_zones == ["zone.active_zone"]


@pytest.mark.usefixtures("improved_presence_detection")
async def test_active_zone_prefers_smaller_zone_if_same_distance(
    hass: HomeAssistant,
) -> None:
    """Test zone size preferences."""
    latitude = 32.880600
    longitude = -117.237561
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Small Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 250,
                },
                {
                    "name": "Big Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 500,
                },
            ]
        },
    )

    active_zone = zone.async_active_zone(hass, latitude, longitude)
    assert active_zone.entity_id == "zone.small_zone"
    active_zone, in_zones = zone.async_in_zones(hass, latitude, longitude)
    assert active_zone.entity_id == "zone.small_zone"
    assert in_zones == ["zone.small_zone", "zone.big_zone"]


@pytest.mark.usefixtures("improved_presence_detection")
async def test_active_zone_prefers_smaller_zone_if_same_distance_2(
    hass: HomeAssistant,
) -> None:
    """Test zone size preferences."""
    latitude = 32.880600
    longitude = -117.237561
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Smallest Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 50,
                }
            ]
        },
    )

    active_zone = zone.async_active_zone(hass, latitude, longitude)
    assert active_zone.entity_id == "zone.smallest_zone"
    active_zone, in_zones = zone.async_in_zones(hass, latitude, longitude)
    assert active_zone.entity_id == "zone.smallest_zone"
    assert in_zones == ["zone.smallest_zone"]


@pytest.mark.usefixtures("improved_presence_detection")
async def test_active_zone_prefers_smaller_zone_over_closer_zone(
    hass: HomeAssistant,
) -> None:
    """Test the smallest containing zone wins over a larger, closer one.

    A larger zone is centered on the point (distance 0) while a smaller zone is
    offset but still contains the point. The smaller zone is farther from its
    center, but it is preferred because it is smaller.
    """
    latitude = 32.880600
    longitude = -117.237561
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Big Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 1000,
                },
                {
                    # Offset ~111 m north; its 200 m radius still contains the
                    # point. Farther from its center than Big Zone, but smaller.
                    "name": "Small Zone",
                    "latitude": latitude + 0.001,
                    "longitude": longitude,
                    "radius": 200,
                },
            ]
        },
    )

    active_zone = zone.async_active_zone(hass, latitude, longitude)
    assert active_zone.entity_id == "zone.small_zone"
    active_zone, in_zones = zone.async_in_zones(hass, latitude, longitude)
    assert active_zone.entity_id == "zone.small_zone"
    assert in_zones == ["zone.small_zone", "zone.big_zone"]


@pytest.mark.usefixtures("improved_presence_detection")
async def test_in_zone_works_for_passive_zones(hass: HomeAssistant) -> None:
    """Test working in passive zones."""
    latitude = 32.880600
    longitude = -117.237561
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Passive Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 250,
                    "passive": True,
                }
            ]
        },
    )

    assert zone.in_zone(hass.states.get("zone.passive_zone"), latitude, longitude)


@pytest.mark.parametrize(
    ("improved_presence_detection", "expected_active_zone", "expected_in_zones"),
    [
        pytest.param(
            False,
            "zone.home",
            ["zone.home", "zone.small_zone", "zone.big_zone"],
            id="overlap",
        ),
        # The accuracy circle only overlaps the home zone
        pytest.param(
            True,
            "zone.small_zone",
            ["zone.small_zone", "zone.big_zone"],
            id="containment",
        ),
    ],
    indirect=["improved_presence_detection"],
)
@pytest.mark.usefixtures("improved_presence_detection")
async def test_async_active_zone_with_non_zero_radius(
    hass: HomeAssistant,
    expected_active_zone: str,
    expected_in_zones: list[str],
) -> None:
    """Test async_active_zone with a non-zero radius."""
    latitude = 32.880600
    longitude = -117.237561

    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Small Zone",
                    "latitude": 32.980600,
                    "longitude": -117.137561,
                    "radius": 50000,
                },
                {
                    "name": "Big Zone",
                    "latitude": 32.980600,
                    "longitude": -117.137561,
                    "radius": 100000,
                },
            ]
        },
    )

    home_state = hass.states.get("zone.home")
    assert home_state.attributes["radius"] == 100
    assert home_state.attributes["latitude"] == 32.87336
    assert home_state.attributes["longitude"] == -117.22743

    active_zone = zone.async_active_zone(hass, latitude, longitude, 5000)
    assert active_zone.entity_id == expected_active_zone
    active_zone, in_zones = zone.async_in_zones(hass, latitude, longitude, 5000)
    assert active_zone.entity_id == expected_active_zone
    assert in_zones == expected_in_zones

    active_zone = zone.async_active_zone(hass, latitude, longitude, 0)
    assert active_zone.entity_id == "zone.small_zone"
    active_zone, in_zones = zone.async_in_zones(hass, latitude, longitude, 0)
    assert active_zone.entity_id == "zone.small_zone"
    assert in_zones == ["zone.small_zone", "zone.big_zone"]


@pytest.mark.parametrize(
    ("latitude", "radius", "expected_relation"),
    [
        pytest.param(0.0, 500, ZoneRelation.CONTAINED, id="contained"),
        pytest.param(0.0, 0, ZoneRelation.CONTAINED, id="contained_point"),
        pytest.param(0.0, None, ZoneRelation.CONTAINED, id="contained_no_accuracy"),
        pytest.param(0.0, 1500, ZoneRelation.OVERLAPPING, id="circle_larger_than_zone"),
        pytest.param(0.018, 1500, ZoneRelation.OVERLAPPING, id="overlapping"),
        pytest.param(0.018, 500, ZoneRelation.SEPARATED, id="separated"),
        pytest.param(0.018, None, ZoneRelation.SEPARATED, id="separated_no_accuracy"),
    ],
)
async def test_zone_relation(
    hass: HomeAssistant,
    latitude: float,
    radius: float | None,
    expected_relation: ZoneRelation,
) -> None:
    """Test the relation between an accuracy circle and a zone."""
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {"zone": [{"name": "Test", "latitude": 0, "longitude": 0, "radius": 1000}]},
    )
    zone_state = hass.states.get("zone.test")

    assert zone.zone_relation(zone_state, latitude, 0, radius) is expected_relation


@pytest.mark.parametrize(
    ("zone_dist", "radius", "expected_relation"),
    [
        pytest.param(600, 400, ZoneRelation.CONTAINED, id="tangent_inside"),
        pytest.param(1400, 400, ZoneRelation.SEPARATED, id="tangent_outside"),
        pytest.param(1000, 0, ZoneRelation.SEPARATED, id="point_on_edge"),
        pytest.param(999, 0, ZoneRelation.CONTAINED, id="point_inside"),
        pytest.param(999, -50, ZoneRelation.CONTAINED, id="negative_radius_inside"),
        pytest.param(1001, -50, ZoneRelation.SEPARATED, id="negative_radius_outside"),
    ],
)
def test_zone_relation_boundaries(
    zone_dist: float, radius: float, expected_relation: ZoneRelation
) -> None:
    """Test the relation at the zone boundary of a zone with radius 1000."""
    assert _zone_relation(zone_dist, 1000, radius) is expected_relation


async def test_zone_relation_unavailable_zone(hass: HomeAssistant) -> None:
    """Test the relation to an unavailable zone can't be calculated."""
    hass.states.async_set("zone.test", STATE_UNAVAILABLE, {})

    assert zone.zone_relation(hass.states.get("zone.test"), 0, 0, 0) is None


@pytest.mark.parametrize(
    (
        "improved_presence_detection",
        "latitude",
        "radius",
        "previous_in_zones",
        "expected_in_zones",
    ),
    [
        pytest.param(False, 0.0, 500, [], ["zone.test"], id="overlap-contained"),
        pytest.param(True, 0.0, 500, [], ["zone.test"], id="containment-contained"),
        pytest.param(
            False, 0.018, 500, ["zone.test"], [], id="overlap-separated_was_inside"
        ),
        pytest.param(
            True, 0.018, 500, ["zone.test"], [], id="containment-separated_was_inside"
        ),
        pytest.param(
            False, 0.018, 1500, [], ["zone.test"], id="overlap-overlapping_was_outside"
        ),
        pytest.param(
            True, 0.018, 1500, [], [], id="containment-overlapping_was_outside"
        ),
        pytest.param(
            False,
            0.018,
            1500,
            ["zone.test"],
            ["zone.test"],
            id="overlap-overlapping_was_inside",
        ),
        pytest.param(
            True,
            0.018,
            1500,
            ["zone.test"],
            ["zone.test"],
            id="containment-overlapping_was_inside",
        ),
        pytest.param(
            True,
            0.0,
            1500,
            ["zone.test"],
            ["zone.test"],
            id="containment-circle_larger_than_zone_was_inside",
        ),
    ],
    indirect=["improved_presence_detection"],
)
@pytest.mark.usefixtures("improved_presence_detection")
async def test_async_in_zones_previous_in_zones(
    hass: HomeAssistant,
    latitude: float,
    radius: float,
    previous_in_zones: list[str],
    expected_in_zones: list[str],
) -> None:
    """Test an overlapping accuracy circle keeps the previous zones."""
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {"zone": [{"name": "Test", "latitude": 0, "longitude": 0, "radius": 1000}]},
    )

    active_zone, in_zones = zone.async_in_zones(
        hass, latitude, 0, radius, previous_in_zones
    )

    assert in_zones == expected_in_zones
    # zone.test is the only zone near the location, so a zone the location is
    # in is also the active zone
    assert [z.entity_id for z in (active_zone,) if z] == expected_in_zones


@pytest.mark.usefixtures("improved_presence_detection")
async def test_async_in_zones_force_overlap(hass: HomeAssistant) -> None:
    """Test force_overlap uses the default overlap test with both methods."""
    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {"zone": [{"name": "Test", "latitude": 0, "longitude": 0, "radius": 1000}]},
    )

    # The accuracy circle only overlaps the zone
    active_zone, in_zones = zone.async_in_zones(
        hass, 0.018, 0, 1500, force_overlap=True
    )
    assert active_zone.entity_id == "zone.test"
    assert in_zones == ["zone.test"]
    assert (
        zone.async_active_zone(hass, 0.018, 0, 1500, force_overlap=True).entity_id
        == "zone.test"
    )


async def test_core_config_update(hass: HomeAssistant) -> None:
    """Test updating core config will update home zone."""
    assert await setup.async_setup_component(hass, "zone", {})

    home = hass.states.get("zone.home")

    await hass.config.async_update(
        location_name="Updated Name", latitude=10, longitude=20
    )
    await hass.async_block_till_done()

    home_updated = hass.states.get("zone.home")

    assert home is not home_updated
    assert home_updated.name == "Updated Name"
    assert home_updated.attributes["latitude"] == 10
    assert home_updated.attributes["longitude"] == 20


async def test_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())

    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"name": "yaml 1", "latitude": 1, "longitude": 2},
                {"name": "yaml 2", "latitude": 3, "longitude": 4},
            ],
        },
    )

    assert count_start + 3 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("zone.yaml_1")
    state_2 = hass.states.get("zone.yaml_2")
    state_3 = hass.states.get("zone.yaml_3")

    assert state_1 is not None
    assert state_1.attributes["latitude"] == 1
    assert state_1.attributes["longitude"] == 2
    assert state_2 is not None
    assert state_2.attributes["latitude"] == 3
    assert state_2.attributes["longitude"] == 4
    assert state_3 is None
    assert len(entity_registry.entities) == 0

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: [
                {"name": "yaml 2", "latitude": 3, "longitude": 4},
                {"name": "yaml 3", "latitude": 5, "longitude": 6},
            ]
        },
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start + 3 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("zone.yaml_1")
    state_2 = hass.states.get("zone.yaml_2")
    state_3 = hass.states.get("zone.yaml_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_2.attributes["latitude"] == 3
    assert state_2.attributes["longitude"] == 4
    assert state_3 is not None
    assert state_3.attributes["latitude"] == 5
    assert state_3.attributes["longitude"] == 6


async def test_load_from_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "0"
    assert state.name == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)


async def test_editable_state_attribute(hass: HomeAssistant, storage_setup) -> None:
    """Test editable attribute."""
    assert await storage_setup(
        config={DOMAIN: [{"name": "yaml option", "latitude": 3, "longitude": 4}]}
    )

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "0"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)

    state = hass.states.get(f"{DOMAIN}.yaml_option")
    assert state.state == "0"
    assert not state.attributes.get(ATTR_EDITABLE)


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing via WS."""
    assert await storage_setup(
        config={DOMAIN: [{"name": "yaml option", "latitude": 3, "longitude": 4}]}
    )

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    storage_ent = "from_storage"
    yaml_ent = "from_yaml"
    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert storage_ent in result
    assert yaml_ent not in result
    assert result[storage_ent][ATTR_NAME] == "from storage"


async def test_ws_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    storage_setup,
) -> None:
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{input_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None


async def test_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    storage_setup,
) -> None:
    """Test updating min/max updates the state."""

    items = [
        {
            "id": "from_storage",
            "name": "from storage",
            "latitude": 1,
            "longitude": 2,
            "radius": 3,
            "passive": False,
        }
    ]
    assert await storage_setup(items)

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state.attributes["latitude"] == 1
    assert state.attributes["longitude"] == 2
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": f"{input_id}",
            "latitude": 3,
            "longitude": 4,
            "passive": True,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.attributes["latitude"] == 3
    assert state.attributes["longitude"] == 4
    assert state.attributes["passive"] is True


async def test_ws_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    storage_setup,
) -> None:
    """Test create WS."""
    assert await storage_setup(items=[])

    input_id = "new_input"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/create",
            "name": "New Input",
            "latitude": 3,
            "longitude": 4,
            "passive": True,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.state == "0"
    assert state.attributes["latitude"] == 3
    assert state.attributes["longitude"] == 4
    assert state.attributes["passive"] is True


async def test_import_config_entry(hass: HomeAssistant) -> None:
    """Test we import config entry and then delete it."""
    entry = MockConfigEntry(
        domain="zone",
        data={
            "name": "from config entry",
            "latitude": 1,
            "longitude": 2,
            "radius": 3,
            "passive": False,
            "icon": "mdi:from-config-entry",
        },
    )
    entry.add_to_hass(hass)
    assert await setup.async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries()) == 0

    state = hass.states.get("zone.from_config_entry")
    assert state is not None
    assert state.attributes[ATTR_LATITUDE] == 1
    assert state.attributes[ATTR_LONGITUDE] == 2
    assert state.attributes[zone.ATTR_RADIUS] == 3
    assert state.attributes[zone.ATTR_PASSIVE] is False
    assert state.attributes[ATTR_ICON] == "mdi:from-config-entry"


async def test_zone_empty_setup(hass: HomeAssistant) -> None:
    """Set up zone with empty config."""
    assert await setup.async_setup_component(hass, DOMAIN, {"zone": {}})


@pytest.mark.usefixtures("improved_presence_detection")
async def test_unavailable_zone(hass: HomeAssistant) -> None:
    """Test active zone with unavailable zones.

    Simulates the startup window where a zone has been pre-filled by the entity
    registry as ``unavailable`` (``restored: True``) before the zone integration
    has had a chance to write the zone's real state. Storage-created zones, and
    YAML zones with an explicit ``id:``, get a unique_id and so are registered
    in the entity registry; on ``EVENT_HOMEASSISTANT_START`` the registry writes
    ``unavailable`` for any such registered entity that does not yet have a
    state. The zone helpers must skip these placeholder states.
    """
    assert await setup.async_setup_component(hass, DOMAIN, {"zone": {}})
    hass.states.async_set("zone.bla", "unavailable", {"restored": True})

    assert zone.async_active_zone(hass, 0.0, 0.01) is None
    active_zone, in_zones = zone.async_in_zones(hass, 0.0, 0.01)
    assert active_zone is None
    assert in_zones == []

    assert zone.in_zone(hass.states.get("zone.bla"), 0, 0) is False


async def test_async_get_enclosing_zones(hass: HomeAssistant) -> None:
    """Test async_get_enclosing_zones returns zones that fully contain the given zone."""
    latitude = 32.880600
    longitude = -117.237561

    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Small Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 100,
                },
                {
                    "name": "Medium Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 500,
                },
                {
                    "name": "Big Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 2000,
                },
                {
                    "name": "Passive Big Zone",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 3000,
                    "passive": True,
                },
            ]
        },
    )

    # Small zone is enclosed by every larger concentric zone, sorted by radius.
    # The queried zone itself is excluded.
    assert zone.async_get_enclosing_zones(hass, "zone.small_zone") == [
        "zone.medium_zone",
        "zone.big_zone",
        "zone.passive_big_zone",
    ]

    # Medium zone is enclosed only by the two bigger zones.
    assert zone.async_get_enclosing_zones(hass, "zone.medium_zone") == [
        "zone.big_zone",
        "zone.passive_big_zone",
    ]

    # The biggest active zone is enclosed by the passive zone only.
    assert zone.async_get_enclosing_zones(hass, "zone.big_zone") == [
        "zone.passive_big_zone",
    ]

    # The largest zone of all is enclosed by nothing.
    assert zone.async_get_enclosing_zones(hass, "zone.passive_big_zone") == []


async def test_async_get_enclosing_zones_equal_radius(hass: HomeAssistant) -> None:
    """Test that same-center same-radius zones enclose each other (<= predicate)."""
    latitude = 32.880600
    longitude = -117.237561

    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Zone A",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 1000,
                },
                {
                    "name": "Zone B",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 1000,
                },
            ]
        },
    )

    assert zone.async_get_enclosing_zones(hass, "zone.zone_a") == ["zone.zone_b"]
    assert zone.async_get_enclosing_zones(hass, "zone.zone_b") == ["zone.zone_a"]


async def test_async_get_enclosing_zones_with_offset(hass: HomeAssistant) -> None:
    """Test full containment accounts for distance from zone center."""
    latitude = 32.880600
    longitude = -117.237561

    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Inner",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 100,
                },
                {
                    "name": "Centered",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 1000,
                },
                {
                    "name": "Offset",
                    "latitude": 32.880600,
                    "longitude": -117.245561,  # ~750m to the west
                    "radius": 1000,
                },
            ]
        },
    )

    # 100m radius zone at the center: both 1000m zones enclose it
    # (centered trivially; offset has ~750 + 100 = 850 <= 1000).
    assert zone.async_get_enclosing_zones(hass, "zone.inner") == [
        "zone.centered",
        "zone.offset",
    ]


async def test_async_get_enclosing_zones_missing_zone(hass: HomeAssistant) -> None:
    """Test async_get_enclosing_zones returns [] for an unknown zone."""
    assert await setup.async_setup_component(hass, DOMAIN, {"zone": {}})

    assert zone.async_get_enclosing_zones(hass, "zone.does_not_exist") == []


async def test_async_get_enclosing_zones_unavailable_input(hass: HomeAssistant) -> None:
    """Test async_get_enclosing_zones returns [] when the input zone is unavailable.

    Simulates the startup window where a zone has been pre-filled by the entity
    registry as ``unavailable`` (``restored: True``) before the zone integration
    has had a chance to write the zone's real state. See ``test_unavailable_zone``
    for the full explanation.
    """
    assert await setup.async_setup_component(hass, DOMAIN, {"zone": {}})
    hass.states.async_set(
        "zone.bla",
        "unavailable",
        {"restored": True},
    )

    assert zone.async_get_enclosing_zones(hass, "zone.bla") == []


async def test_async_get_enclosing_zones_skips_unavailable_other(
    hass: HomeAssistant,
) -> None:
    """Test other zones that are unavailable are skipped when searching containers.

    See ``test_unavailable_zone`` for why an unavailable zone can appear in the
    state machine.
    """
    latitude = 32.880600
    longitude = -117.237561

    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Inner",
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": 100,
                },
            ]
        },
    )
    # A zone that would otherwise enclose Inner, but is unavailable.
    hass.states.async_set(
        "zone.bigger",
        "unavailable",
        {
            ATTR_LATITUDE: latitude,
            ATTR_LONGITUDE: longitude,
            ATTR_RADIUS: 1000,
            "restored": True,
        },
    )

    assert zone.async_get_enclosing_zones(hass, "zone.inner") == []


@pytest.mark.parametrize(
    (
        "tracked_domain",
        "tracked_attr",
        "untracked_attr",
        "test_zone_states",
        "home_states",
    ),
    [
        pytest.param(
            "person",
            ZoneEntityStateAttribute.PERSONS,
            ZoneEntityStateAttribute.DEVICE_TRACKERS,
            ["0", "1", "2", "1", "2", "1", "0"],
            ["0", "0", "0", "1", "1", "0", "0"],
            id="person",
        ),
        pytest.param(
            "device_tracker",
            ZoneEntityStateAttribute.DEVICE_TRACKERS,
            ZoneEntityStateAttribute.PERSONS,
            # Device trackers are not counted towards the zone state.
            ["0", "0", "0", "0", "0", "0", "0"],
            ["0", "0", "0", "0", "0", "0", "0"],
            id="device_tracker",
        ),
    ],
)
async def test_state(
    hass: HomeAssistant,
    tracked_domain: str,
    tracked_attr: ZoneEntityStateAttribute,
    untracked_attr: ZoneEntityStateAttribute,
    test_zone_states: list[str],
    home_states: list[str],
) -> None:
    """Test the state and the persons / device_trackers attributes of a zone."""
    one = f"{tracked_domain}.one"
    two = f"{tracked_domain}.two"

    info = {
        "name": "Test Zone",
        "latitude": 32.880837,
        "longitude": -117.237561,
        "radius": 250,
        "passive": False,
    }
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})
    assert len(hass.states.async_entity_ids(DOMAIN)) == 2

    def assert_zone(
        entity_id: str, expected_state: str, expected_tracked: list[str]
    ) -> None:
        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_state
        assert sorted(state.attributes[tracked_attr]) == expected_tracked
        # The other collection must stay empty, they are tracked independently.
        assert state.attributes[untracked_attr] == []

    assert_zone("zone.test_zone", test_zone_states[0], [])
    assert_zone("zone.home", home_states[0], [])

    # Entity enters the zone
    hass.states.async_set(
        one, "Test Zone", {device_tracker.ATTR_IN_ZONES: ["zone.test_zone"]}
    )
    await hass.async_block_till_done()
    assert_zone("zone.test_zone", test_zone_states[1], [one])
    assert_zone("zone.home", home_states[1], [])

    # A second entity enters the zone (case insensitive state)
    hass.states.async_set(
        two, "TEST zone", {device_tracker.ATTR_IN_ZONES: ["zone.test_zone"]}
    )
    await hass.async_block_till_done()
    assert_zone("zone.test_zone", test_zone_states[2], sorted([one, two]))
    assert_zone("zone.home", home_states[2], [])

    # The first entity moves to another zone
    hass.states.async_set(one, "home", {device_tracker.ATTR_IN_ZONES: ["zone.home"]})
    await hass.async_block_till_done()
    assert_zone("zone.test_zone", test_zone_states[3], [two])
    assert_zone("zone.home", home_states[3], [one])

    # The first entity is in two zones
    hass.states.async_set(
        one, "home", {device_tracker.ATTR_IN_ZONES: ["zone.home", "zone.test_zone"]}
    )
    await hass.async_block_till_done()
    assert_zone("zone.test_zone", test_zone_states[4], sorted([one, two]))
    assert_zone("zone.home", home_states[4], [one])

    # The first entity enters not_home
    hass.states.async_set(one, "not_home", {device_tracker.ATTR_IN_ZONES: []})
    await hass.async_block_till_done()
    assert_zone("zone.test_zone", test_zone_states[5], [two])
    assert_zone("zone.home", home_states[5], [])

    # The second entity is removed
    hass.states.async_remove(two)
    await hass.async_block_till_done()
    assert_zone("zone.test_zone", test_zone_states[6], [])
    assert_zone("zone.home", home_states[6], [])


async def test_persons_and_device_trackers_tracked_independently(
    hass: HomeAssistant,
) -> None:
    """Test persons and device trackers in the same zone don't interfere."""
    info = {
        "name": "Test Zone",
        "latitude": 32.880837,
        "longitude": -117.237561,
        "radius": 250,
        "passive": False,
    }
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})

    hass.states.async_set(
        "person.person1",
        "Test Zone",
        {device_tracker.ATTR_IN_ZONES: ["zone.test_zone"]},
    )
    hass.states.async_set(
        "device_tracker.tracker1",
        "Test Zone",
        {device_tracker.ATTR_IN_ZONES: ["zone.test_zone"]},
    )
    await hass.async_block_till_done()

    state = hass.states.get("zone.test_zone")
    assert state
    # Only persons are counted towards the state.
    assert state.state == "1"
    assert state.attributes[ZoneEntityStateAttribute.PERSONS] == ["person.person1"]
    assert state.attributes[ZoneEntityStateAttribute.DEVICE_TRACKERS] == [
        "device_tracker.tracker1"
    ]


async def test_trackers_present_before_zone_setup(hass: HomeAssistant) -> None:
    """Test persons and device trackers already in a zone at setup are picked up."""
    hass.states.async_set(
        "person.person1",
        "Test Zone",
        {device_tracker.ATTR_IN_ZONES: ["zone.test_zone"]},
    )
    hass.states.async_set(
        "device_tracker.tracker1",
        "Test Zone",
        {device_tracker.ATTR_IN_ZONES: ["zone.test_zone"]},
    )

    info = {
        "name": "Test Zone",
        "latitude": 32.880837,
        "longitude": -117.237561,
        "radius": 250,
        "passive": False,
    }
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})
    await hass.async_block_till_done()

    state = hass.states.get("zone.test_zone")
    assert state
    assert state.state == "1"
    assert state.attributes[ZoneEntityStateAttribute.PERSONS] == ["person.person1"]
    assert state.attributes[ZoneEntityStateAttribute.DEVICE_TRACKERS] == [
        "device_tracker.tracker1"
    ]
