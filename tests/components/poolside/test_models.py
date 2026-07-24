"""Tests for parsing Site.getControlLayout and Site.getPoolDevices responses."""

from homeassistant.components.poolside.const import ControlType, GroupKind
from homeassistant.components.poolside.models import (
    PoolsideDevice,
    parse_control_layout,
    parse_pool_devices,
)

LAYOUT = {
    "SiteName": "Smith Residence",
    "SiteUUID": "site-smith",
    "Groups": [
        {
            "UUID": "group-pool",
            "Name": "Pool",
            "Kind": "BODY_OF_WATER",
            "BodyOfWaterUUID": "bow-pool",
            "BodyOfWaterName": "Pool",
            "BodyOfWaterType": "POOL",
            "Controls": [
                {
                    "UUID": "heater-1",
                    "Name": "Heater",
                    "ControlType": "TEMPERATURE",
                    "MinSetPoint": 40,
                    "MaxSetPoint": 104,
                },
                {
                    "UUID": "light-1",
                    "Name": "Light",
                    "ControlType": "LIGHT",
                    "SupportsColors": True,
                },
                {
                    "UUID": "filter-1",
                    "Name": "Filter",
                    "ControlType": "FILTER",
                    "ControlItemUUID": "item-filter-1",
                    "SpeedIncrements": [25, 50, 75, 100],
                },
                {
                    "UUID": "combined-1",
                    "Name": "Combined Light",
                    "ControlType": "LIGHT",
                    "MemberControlUUIDs": ["light-a", "light-b"],
                },
                {
                    "UUID": "light-a",
                    "Name": "Light A",
                    "ControlType": "LIGHT",
                    "CombinedControlUUID": "combined-1",
                    "SupportsColors": True,
                    "DefaultColor": "Ocean Blue",
                },
                {
                    "UUID": "light-b",
                    "Name": "Light B",
                    "ControlType": "LIGHT",
                    "CombinedControlUUID": "combined-1",
                },
                {
                    "UUID": "winter-pump",
                    "Name": "Winter Pump",
                    "ControlType": "FILTER",
                    "Winterized": True,
                },
                {
                    "UUID": "fire-feature-1",
                    "Name": "Fire Feature",
                    "ControlType": "FIRE_FEATURE",
                },
            ],
        },
        {
            "UUID": "backyard",
            "Name": "Landscape",
            "Kind": "LANDSCAPE",
            "Controls": [
                {
                    "UUID": "landscape-light",
                    "Name": "Path Lights",
                    "ControlType": "LIGHT",
                }
            ],
        },
    ],
}


def test_parse_control_layout_site_name() -> None:
    """The site name is read from the top-level SiteName field."""
    site, _controls = parse_control_layout(LAYOUT)
    assert site.name == "Smith Residence"


def test_parse_control_layout_site_uuid() -> None:
    """The site UUID is read from the top-level SiteUUID field."""
    site, _controls = parse_control_layout(LAYOUT)
    assert site.uuid == "site-smith"


def test_parse_control_layout_site_uuid_missing() -> None:
    """Older firmware without a site UUID yields a site with uuid=None."""
    layout = {**LAYOUT}
    del layout["SiteUUID"]
    site, _controls = parse_control_layout(layout)
    assert site.uuid is None


def test_parse_control_layout_flattens_groups() -> None:
    """Controls from every group are flattened into a single list."""
    _site, controls = parse_control_layout(LAYOUT)
    uuids = {control.uuid for control in controls}
    assert "landscape-light" in uuids
    assert "heater-1" in uuids


def test_parse_control_layout_skips_combined_members() -> None:
    """Combined control members are skipped; the combined control itself is kept."""
    _site, controls = parse_control_layout(LAYOUT)
    uuids = {control.uuid for control in controls}
    assert "combined-1" in uuids
    assert "light-a" not in uuids
    assert "light-b" not in uuids


def test_parse_control_layout_group_kind_and_body_of_water_type() -> None:
    """Each control's group carries its Kind and, for a body of water, its type."""
    _site, controls = parse_control_layout(LAYOUT)
    by_uuid = {control.uuid: control for control in controls}

    pool_group = by_uuid["heater-1"].group
    assert pool_group.kind is GroupKind.BODY_OF_WATER
    assert pool_group.name == "Pool"
    assert pool_group.body_of_water_type == "POOL"

    landscape_group = by_uuid["landscape-light"].group
    assert landscape_group.kind is GroupKind.LANDSCAPE


def test_control_type_parsed_from_control_type_field() -> None:
    """ControlType values map onto the ControlType enum."""
    _site, controls = parse_control_layout(LAYOUT)
    by_uuid = {control.uuid: control for control in controls}
    assert by_uuid["heater-1"].control_type is ControlType.TEMPERATURE
    assert by_uuid["light-1"].control_type is ControlType.LIGHT
    assert by_uuid["filter-1"].control_type is ControlType.FILTER


def test_control_set_point_bounds() -> None:
    """MinSetPoint/MaxSetPoint surface as float properties."""
    _site, controls = parse_control_layout(LAYOUT)
    heater = next(c for c in controls if c.uuid == "heater-1")
    assert heater.min_set_point == 40
    assert heater.max_set_point == 104


def test_control_set_point_bounds_tolerate_string_values() -> None:
    """MinSetPoint/MaxSetPoint may arrive stringly-typed; they still coerce to float."""
    layout = {
        "SiteName": "Test",
        "Groups": [
            {
                "UUID": "group-1",
                "Name": "Pool",
                "Kind": "BODY_OF_WATER",
                "Controls": [
                    {
                        "UUID": "heater-2",
                        "Name": "Heater",
                        "ControlType": "TEMPERATURE",
                        "MinSetPoint": "40",
                        "MaxSetPoint": "104",
                    }
                ],
            }
        ],
    }
    _site, controls = parse_control_layout(layout)
    heater = controls[0]
    assert heater.min_set_point == 40.0
    assert heater.max_set_point == 104.0


def test_control_speed_increments_and_variable_speed() -> None:
    """A control's speed increments determine whether it's variable-speed."""
    _site, controls = parse_control_layout(LAYOUT)
    by_uuid = {control.uuid: control for control in controls}

    variable_speed = by_uuid["filter-1"]
    assert variable_speed.speed_increments == [25, 50, 75, 100]
    assert variable_speed.is_variable_speed

    plain_on_off = by_uuid["winter-pump"]
    assert plain_on_off.speed_increments == [100]
    assert not plain_on_off.is_variable_speed


def test_control_winterized() -> None:
    """Winterized controls are flagged so entities can go unavailable."""
    _site, controls = parse_control_layout(LAYOUT)
    by_uuid = {control.uuid: control for control in controls}
    assert by_uuid["winter-pump"].winterized
    assert not by_uuid["heater-1"].winterized


def test_unrecognized_control_type_maps_to_unknown() -> None:
    """A ControlType this integration doesn't classify falls back to UNKNOWN."""
    _site, controls = parse_control_layout(LAYOUT)
    by_uuid = {control.uuid: control for control in controls}
    assert by_uuid["fire-feature-1"].control_type is ControlType.UNKNOWN


def test_status_key_for_temperature_is_body_of_water_uuid() -> None:
    """TEMPERATURE has no ControlItemUUID; status is keyed by the body instead."""
    _site, controls = parse_control_layout(LAYOUT)
    heater = next(c for c in controls if c.uuid == "heater-1")
    assert heater.status_key == "bow-pool"


def test_status_key_ignores_control_item_uuid() -> None:
    """Non-TEMPERATURE controls key on their own UUID, never ControlItemUUID.

    ControlItemUUID identifies the underlying PoolDevice - separate physical
    hardware, not the control - so it must not be used for status routing.
    """
    _site, controls = parse_control_layout(LAYOUT)
    filter_control = next(c for c in controls if c.uuid == "filter-1")
    assert filter_control.status_key == "filter-1"


def test_status_key_falls_back_to_own_uuid() -> None:
    """A non-TEMPERATURE control (with or without a ControlItemUUID) uses its own UUID."""
    _site, controls = parse_control_layout(LAYOUT)
    light = next(c for c in controls if c.uuid == "light-1")
    assert light.status_key == "light-1"


def test_combined_control_inherits_capability_from_first_member() -> None:
    """A combined control's missing layout capabilities come from its first member."""
    _site, controls = parse_control_layout(LAYOUT)
    combined = next(c for c in controls if c.uuid == "combined-1")
    assert combined.capability("SupportsColors") is True
    assert combined.capability("DefaultColor") == "Ocean Blue"
    # The combined control's own identity is never overwritten by the member.
    assert combined.name == "Combined Light"


def test_combined_control_exposes_member_uuids() -> None:
    """A combined control's member UUIDs are available for status routing."""
    _site, controls = parse_control_layout(LAYOUT)
    combined = next(c for c in controls if c.uuid == "combined-1")
    assert combined.member_uuids == ["light-a", "light-b"]

    non_combined = next(c for c in controls if c.uuid == "heater-1")
    assert non_combined.member_uuids == []


def test_parse_pool_devices() -> None:
    """Devices parse from Site.getPoolDevices; UUID-less entries are skipped."""
    devices = parse_pool_devices(
        {
            "SiteUUID": "site-smith",
            "Devices": [
                {"UUID": "pump-1", "Name": "Main Pump", "DeviceType": "Pump"},
                {"Name": "Ghost", "DeviceType": "Pump"},
            ],
        }
    )
    assert devices == [
        PoolsideDevice(uuid="pump-1", name="Main Pump", device_type="Pump")
    ]


def test_parse_pool_devices_name_falls_back_to_device_type() -> None:
    """A device without a configured name is named after its type."""
    devices = parse_pool_devices(
        {"Devices": [{"UUID": "heater-1", "DeviceType": "Heater"}]}
    )
    assert devices == [
        PoolsideDevice(uuid="heater-1", name="Heater", device_type="Heater")
    ]
