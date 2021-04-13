"""Test zone component."""
import math
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components import zone
from homeassistant.components.zone import DOMAIN
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.util.location import vincenty

from tests.common import MockConfigEntry


@pytest.fixture
def storage_setup(hass, hass_storage):
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


# Author: https://github.com/pktrigg
# Source: https://github.com/pktrigg/pyall/blob/master/geodetic.py
# License: https://github.com/pktrigg/pyall/blob/master/LICENSE
def calculateGeographicalPositionFromRangeBearing(latitude1, longitude1, alpha1To2, s):
    """
    Calculate new position giving starting position, bearing and distance.

    Returns the lat and long of projected point and reverse azimuth
    given a reference point and a distance and azimuth to project.
    lats, longs and azimuths are passed in decimal degrees
    Returns ( latitude2,  longitude2,  alpha2To1 ) as a tuple
    """
    if math.isclose(s, 0):
        return (latitude1, longitude1, s)

    f = 1.0 / 298.257223563  # WGS84
    a = 6378137.0  # metres

    piD4 = math.atan(1.0)
    two_pi = piD4 * 8.0

    latitude1 = latitude1 * piD4 / 45.0
    longitude1 = longitude1 * piD4 / 45.0
    alpha1To2 = alpha1To2 * piD4 / 45.0
    if alpha1To2 < 0.0:
        alpha1To2 = alpha1To2 + two_pi
    if alpha1To2 > two_pi:
        alpha1To2 = alpha1To2 - two_pi

    b = a * (1.0 - f)

    TanU1 = (1 - f) * math.tan(latitude1)
    U1 = math.atan(TanU1)
    sigma1 = math.atan2(TanU1, math.cos(alpha1To2))
    Sinalpha = math.cos(U1) * math.sin(alpha1To2)
    cosalpha_sq = 1.0 - Sinalpha * Sinalpha

    u2 = cosalpha_sq * (a * a - b * b) / (b * b)
    A = 1.0 + (u2 / 16384) * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = (u2 / 1024) * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))

    # Starting with the approximation
    sigma = s / (b * A)

    last_sigma = 2.0 * sigma + 2.0  # something impossible

    # Iterate the following three equations
    # until there is no significant change in sigma

    # two_sigma_m , delta_sigma
    while abs((last_sigma - sigma) / sigma) > 1.0e-9:
        two_sigma_m = 2 * sigma1 + sigma

        delta_sigma = (
            B
            * math.sin(sigma)
            * (
                math.cos(two_sigma_m)
                + (B / 4)
                * (
                    math.cos(sigma)
                    * (
                        -1
                        + 2 * math.pow(math.cos(two_sigma_m), 2)
                        - (B / 6)
                        * math.cos(two_sigma_m)
                        * (-3 + 4 * math.pow(math.sin(sigma), 2))
                        * (-3 + 4 * math.pow(math.cos(two_sigma_m), 2))
                    )
                )
            )
        )
        last_sigma = sigma
        sigma = (s / (b * A)) + delta_sigma

    latitude2 = math.atan2(
        (
            math.sin(U1) * math.cos(sigma)
            + math.cos(U1) * math.sin(sigma) * math.cos(alpha1To2)
        ),
        (
            (1 - f)
            * math.sqrt(
                math.pow(Sinalpha, 2)
                + pow(
                    math.sin(U1) * math.sin(sigma)
                    - math.cos(U1) * math.cos(sigma) * math.cos(alpha1To2),
                    2,
                )
            )
        ),
    )

    # Intentional misspelling to not collide with lambda keyword
    lembda = math.atan2(
        (math.sin(sigma) * math.sin(alpha1To2)),
        (
            math.cos(U1) * math.cos(sigma)
            - math.sin(U1) * math.sin(sigma) * math.cos(alpha1To2)
        ),
    )

    C = (f / 16) * cosalpha_sq * (4 + f * (4 - 3 * cosalpha_sq))

    omega = lembda - (1 - C) * f * Sinalpha * (
        sigma
        + C
        * math.sin(sigma)
        * (
            math.cos(two_sigma_m)
            + C * math.cos(sigma) * (-1 + 2 * math.pow(math.cos(two_sigma_m), 2))
        )
    )

    longitude2 = longitude1 + omega

    alpha21 = math.atan2(
        Sinalpha,
        (
            -math.sin(U1) * math.sin(sigma)
            + math.cos(U1) * math.cos(sigma) * math.cos(alpha1To2)
        ),
    )

    alpha21 = alpha21 + two_pi / 2.0
    if alpha21 < 0.0:
        alpha21 = alpha21 + two_pi
    if alpha21 > two_pi:
        alpha21 = alpha21 - two_pi

    latitude2 = latitude2 * 45.0 / piD4
    longitude2 = longitude2 * 45.0 / piD4
    alpha21 = alpha21 * 45.0 / piD4

    return latitude2, longitude2, alpha21


def calculate_postion_from_distance(position, distance):
    """Calculate new position giving initial position and distance.

    Asserts that the result is in accordance with inverse vincenty from location util.
    """
    lat, lon, _ = calculateGeographicalPositionFromRangeBearing(
        position[0], position[1], 0, distance
    )

    # Verify that the distance to the calculated position is correct
    assert -0.1 < distance - vincenty((lat, lon), position) * 1000 < 0.1

    return (lat, lon)


async def test_setup_no_zones_still_adds_home_zone(hass):
    """Test if no config is passed in we still get the home zone."""
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": None})
    assert len(hass.states.async_entity_ids("zone")) == 1
    state = hass.states.get("zone.home")
    assert hass.config.location_name == state.name
    assert hass.config.latitude == state.attributes["latitude"]
    assert hass.config.longitude == state.attributes["longitude"]
    assert not state.attributes.get("passive", False)


async def test_setup(hass):
    """Test a successful setup."""
    info = {
        "name": "Test Zone",
        "latitude": 32.880837,
        "longitude": -117.237561,
        "radius": 250,
        "passive": True,
    }
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})

    assert len(hass.states.async_entity_ids("zone")) == 2
    state = hass.states.get("zone.test_zone")
    assert info["name"] == state.name
    assert info["latitude"] == state.attributes["latitude"]
    assert info["longitude"] == state.attributes["longitude"]
    assert info["radius"] == state.attributes["radius"]
    assert info["passive"] == state.attributes["passive"]


async def test_setup_zone_skips_home_zone(hass):
    """Test that zone named Home should override hass home zone."""
    info = {"name": "Home", "latitude": 1.1, "longitude": -2.2}
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": info})

    assert len(hass.states.async_entity_ids("zone")) == 1
    state = hass.states.get("zone.home")
    assert info["name"] == state.name


async def test_setup_name_can_be_same_on_multiple_zones(hass):
    """Test that zone named Home should override hass home zone."""
    info = {"name": "Test Zone", "latitude": 1.1, "longitude": -2.2}
    assert await setup.async_setup_component(hass, zone.DOMAIN, {"zone": [info, info]})
    assert len(hass.states.async_entity_ids("zone")) == 3


async def test_active_zone_skips_passive_zones(hass):
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
    active = zone.async_active_zone(hass, 32.880600, -117.237561)
    assert active is None


async def test_active_zone_skips_passive_zones_2(hass):
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
    active = zone.async_active_zone(hass, 32.880700, -117.237561)
    assert active.entity_id == "zone.active_zone"


async def test_active_zone_prefers_smaller_zone_if_same_distance(hass):
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

    active = zone.async_active_zone(hass, latitude, longitude)
    assert active.entity_id == "zone.small_zone"


async def test_active_zone_prefers_smaller_zone_if_same_distance_2(hass):
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

    active = zone.async_active_zone(hass, latitude, longitude)
    assert active.entity_id == "zone.smallest_zone"


async def test_zone_smaller_than_accuracy(hass):
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

    # Should not enter zone, accuracy is poor
    active = zone.async_active_zone(hass, latitude, longitude, 51)
    assert active is None

    # Should enter zone, accuracy is good enough
    active = zone.async_active_zone(hass, latitude, longitude, 49, active)
    assert active.entity_id == "zone.smallest_zone"

    # Should remain in zone
    active = zone.async_active_zone(hass, latitude, longitude, 51, active)
    assert active.entity_id == "zone.smallest_zone"


def assert_zone(zone, expected_zone, idx):
    """Assert current zone is the expected one.

    Unused parameter idx added to get useful debug information from pytest.
    """
    if expected_zone is None:
        assert zone is None
    else:
        assert zone.entity_id == f"zone.{expected_zone}"


@pytest.mark.parametrize(
    "zone_settings,locations,expected_zones",
    # zone settings: (distance from origin, radius) for each configured zone
    # locations: list of (distance, accuracy) from starting location
    # expected zones: list of expected zone for each location in the locations list
    [
        # Test concentric zones
        # Don't enter a zone smaller than the location's accuracy
        (
            [(0, 6), (0, 12)],
            [(0, 12), (0, 11.9), (0, 3)],
            [None, "kebab_shop_garden", "kebab_shop"],
        ),
        # Test concentric zones
        # Don't leave a zone if location with accuracy intersects with zone
        (
            [(0, 6), (0, 12)],
            [(0, 3), (0, 11.9), (0, 12)],
            ["kebab_shop", "kebab_shop", "kebab_shop"],
        ),
        # Test concentric zones
        # Exit a zone if location with accuracy does not intersect with zone
        # In this test we expect to jump directly from inner zone to no zone
        (
            [(0, 6), (0, 11)],
            [(0, 3), (6, 3), (9, 3), (6, 3)],
            ["kebab_shop", "kebab_shop", None, "kebab_shop_garden"],
        ),
        # Test concentric zones
        # Exit a zone if location with accuracy does not intersect with zone
        # In this test we expect to jump from inner zone to outer zone
        (
            [(0, 6), (0, 13)],
            [(0, 3), (6, 3), (9, 3), (6, 3)],
            ["kebab_shop", "kebab_shop", "kebab_shop_garden", "kebab_shop_garden"],
        ),
        # Non concentric zones
        # Exit a zone if location with accuracy does not intersect with zone
        # In this test we expect to jump from first zone to second zone via no zone
        (
            [(0, 6), (12, 6)],
            [(0, 3), (6, 3), (9, 3), (12, 3)],
            ["kebab_shop", "kebab_shop", None, "kebab_shop_garden"],
        ),
        # Non concentric zones
        # Exit a zone if location with accuracy does not intersect with zone
        # In this test we expect to jump directly from first zone to second zone
        (
            [(0, 6), (9, 6)],
            [(0, 3), (6, 3), (9, 3), (6, 3)],
            ["kebab_shop", "kebab_shop", "kebab_shop_garden", "kebab_shop_garden"],
        ),
    ],
)
async def test_zone_criteria(hass, zone_settings, locations, expected_zones):
    """Test zone enter and exit criteria."""
    origin = (55.69991353346531, 13.206717073911985)
    zone_locations = []

    for setting in zone_settings:
        lat, lon = calculate_postion_from_distance(origin, setting[0])
        zone_locations.append((lat, lon, setting[1]))

    assert await setup.async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Kebab shop",
                    "latitude": zone_locations[0][0],
                    "longitude": zone_locations[0][1],
                    "radius": zone_locations[0][2],
                },
                {
                    "name": "Kebab shop garden",
                    "latitude": zone_locations[1][0],
                    "longitude": zone_locations[1][1],
                    "radius": zone_locations[1][2],
                },
            ]
        },
    )

    active = None
    for idx, location in enumerate(locations):
        distance, radius = location
        # Calculate new location
        lat, lon = calculate_postion_from_distance(origin, distance)
        active = zone.async_active_zone(hass, lat, lon, radius, active)
        expected_zone = expected_zones[idx]
        assert_zone(active, expected_zone, idx)


async def test_in_zone_works_for_passive_zones(hass):
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


async def test_core_config_update(hass):
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


async def test_reload(hass, hass_admin_user, hass_read_only_user):
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())
    ent_reg = er.async_get(hass)

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
    assert len(ent_reg.entities) == 0

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


async def test_load_from_storage(hass, storage_setup):
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "zoning"
    assert state.name == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)


async def test_editable_state_attribute(hass, storage_setup):
    """Test editable attribute."""
    assert await storage_setup(
        config={DOMAIN: [{"name": "yaml option", "latitude": 3, "longitude": 4}]}
    )

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "zoning"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)

    state = hass.states.get(f"{DOMAIN}.yaml_option")
    assert state.state == "zoning"
    assert not state.attributes.get(ATTR_EDITABLE)


async def test_ws_list(hass, hass_ws_client, storage_setup):
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


async def test_ws_delete(hass, hass_ws_client, storage_setup):
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"
    ent_reg = er.async_get(hass)

    state = hass.states.get(input_entity_id)
    assert state is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{input_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None


async def test_update(hass, hass_ws_client, storage_setup):
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
    ent_reg = er.async_get(hass)

    state = hass.states.get(input_entity_id)
    assert state.attributes["latitude"] == 1
    assert state.attributes["longitude"] == 2
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

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


async def test_ws_create(hass, hass_ws_client, storage_setup):
    """Test create WS."""
    assert await storage_setup(items=[])

    input_id = "new_input"
    input_entity_id = f"{DOMAIN}.{input_id}"
    ent_reg = er.async_get(hass)

    state = hass.states.get(input_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None

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
    assert state.state == "zoning"
    assert state.attributes["latitude"] == 3
    assert state.attributes["longitude"] == 4
    assert state.attributes["passive"] is True


async def test_import_config_entry(hass):
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
    assert state.attributes[zone.ATTR_LATITUDE] == 1
    assert state.attributes[zone.ATTR_LONGITUDE] == 2
    assert state.attributes[zone.ATTR_RADIUS] == 3
    assert state.attributes[zone.ATTR_PASSIVE] is False
    assert state.attributes[ATTR_ICON] == "mdi:from-config-entry"


async def test_zone_empty_setup(hass):
    """Set up zone with empty config."""
    assert await setup.async_setup_component(hass, DOMAIN, {"zone": {}})


async def test_unavailable_zone(hass):
    """Test active zone with unavailable zones."""
    assert await setup.async_setup_component(hass, DOMAIN, {"zone": {}})
    hass.states.async_set("zone.bla", "unavailable", {"restored": True})

    assert zone.async_active_zone(hass, 0.0, 0.01) is None

    assert zone.in_zone(hass.states.get("zone.bla"), 0, 0) is False
