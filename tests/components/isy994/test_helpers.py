"""Tests for ISY994 helper functions."""

from unittest.mock import MagicMock

from pyisy.constants import (
    BACKLIGHT_SUPPORT,
    CMD_BACKLIGHT,
    ISY_VALUE_UNKNOWN,
    PROTO_INSTEON,
    PROTO_ZWAVE,
    UOM_INDEX,
)
from pyisy.helpers import ZWaveProperties
from pyisy.nodes import Node
import pytest

from homeassistant.components.isy994.const import (
    FILTER_INSTEON_TYPE,
    FILTER_NODE_DEF_ID,
    FILTER_UOM,
    FILTER_ZWAVE_CAT,
    NODE_FILTERS,
    SUBNODE_CLIMATE_COOL,
    SUBNODE_FANLINC_LIGHT,
    SUBNODE_IOLINC_RELAY,
    UOM_DOUBLE_TEMP,
    UOM_ISYV4_DEGREES,
)
from homeassistant.components.isy994.helpers import (
    _add_backlight_if_supported,
    _check_for_insteon_type,
    _check_for_node_def,
    _check_for_states_in_uom,
    _check_for_uom_id,
    _check_for_zwave_cat,
    _generate_device_info,
    convert_isy_value_to_hass,
)
from homeassistant.components.isy994.models import IsyData
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, Platform

# ---------------------------------------------------------------------------
# convert_isy_value_to_hass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "uom", "precision", "fallback", "expected"),
    [
        pytest.param(None, None, 0, None, None, id="none_value"),
        pytest.param(ISY_VALUE_UNKNOWN, None, 0, None, None, id="unknown_value"),
        pytest.param(1500, UOM_DOUBLE_TEMP, 0, None, 750.0, id="double_temp"),
        pytest.param(2345, UOM_ISYV4_DEGREES, 0, None, 1172.5, id="isyv4_degrees"),
        pytest.param(2345, None, "2", None, 23.45, id="precision_str"),
        pytest.param(2345, None, 2, None, 23.45, id="precision_int"),
        pytest.param(72, None, "0", None, 72, id="precision_zero_str"),
        pytest.param(72, None, 0, None, 72, id="precision_zero_int"),
        pytest.param(72, None, 0, 1, 72.0, id="fallback_precision"),
        pytest.param(72.7, None, 0, 1, 72.7, id="fallback_precision_float"),
    ],
)
def test_convert_isy_value_to_hass(
    value: float | None,
    uom: str | None,
    precision: int | str,
    fallback: int | None,
    expected: float | None,
) -> None:
    """Test convert_isy_value_to_hass with various inputs."""
    result = convert_isy_value_to_hass(value, uom, precision, fallback)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Helper: make a minimal IsyData
# ---------------------------------------------------------------------------


def make_isy_data() -> IsyData:
    """Return a fresh IsyData with no root ISY (only nodes/programs needed)."""
    data = IsyData.__new__(IsyData)
    IsyData.__init__(data)
    return data


def make_node(
    *,
    protocol: str = PROTO_INSTEON,
    address: str = "1 1",
    node_def_id: str | None = None,
    node_type: str | None = None,
) -> MagicMock:
    """Return a mock Node."""
    node = MagicMock(spec=Node)
    node.protocol = protocol
    node.address = address
    node.node_def_id = node_def_id
    node.type = node_type
    node.name = "Test Node"
    node.aux_properties = {}
    return node


# ---------------------------------------------------------------------------
# _check_for_node_def
# ---------------------------------------------------------------------------


def test_check_for_node_def_no_attr() -> None:
    """Node without node_def_id attr returns False."""
    isy_data = make_isy_data()
    node = MagicMock(spec=Node)
    del node.node_def_id
    assert _check_for_node_def(isy_data, node) is False


def test_check_for_node_def_none_value() -> None:
    """Node with node_def_id=None returns False."""
    isy_data = make_isy_data()
    node = make_node(node_def_id=None)
    assert _check_for_node_def(isy_data, node) is False


def test_check_for_node_def_match() -> None:
    """Node whose node_def_id is in the LIGHT filter is added to LIGHT platform."""
    isy_data = make_isy_data()
    light_id = next(iter(NODE_FILTERS[Platform.LIGHT][FILTER_NODE_DEF_ID]))
    node = make_node(node_def_id=light_id)
    result = _check_for_node_def(isy_data, node, single_platform=Platform.LIGHT)
    assert result is True
    assert node in isy_data.nodes[Platform.LIGHT]


def test_check_for_node_def_no_match() -> None:
    """Unknown node_def_id returns False without adding to any platform."""
    isy_data = make_isy_data()
    node = make_node(node_def_id="completely_unknown_def_id")
    assert _check_for_node_def(isy_data, node) is False
    for nodes in isy_data.nodes.values():
        assert node not in nodes


# ---------------------------------------------------------------------------
# _check_for_insteon_type
# ---------------------------------------------------------------------------


def test_check_for_insteon_type_non_insteon() -> None:
    """Non-Insteon protocol returns False immediately."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_ZWAVE)
    assert _check_for_insteon_type(isy_data, node) is False


def test_check_for_insteon_type_no_type_attr() -> None:
    """Insteon node without type attr returns False."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_INSTEON)
    del node.type
    assert _check_for_insteon_type(isy_data, node) is False


def test_check_for_insteon_type_none_type() -> None:
    """Insteon node with type=None returns False."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_INSTEON, node_type=None)
    assert _check_for_insteon_type(isy_data, node) is False


def test_check_for_insteon_type_fanlinc_light_subnode() -> None:
    """FanLinc subnode SUBNODE_FANLINC_LIGHT is placed on LIGHT platform."""
    isy_data = make_isy_data()
    # address last hex segment = SUBNODE_FANLINC_LIGHT (1)
    fan_type = "1.46."
    node = make_node(
        protocol=PROTO_INSTEON,
        address=f"1 {SUBNODE_FANLINC_LIGHT:X}",
        node_type=fan_type,
    )
    result = _check_for_insteon_type(isy_data, node, single_platform=Platform.FAN)
    assert result is True
    assert node in isy_data.nodes[Platform.LIGHT]
    assert node not in isy_data.nodes[Platform.FAN]


def test_check_for_insteon_type_climate_subnode_cool() -> None:
    """Climate cool subnode is placed on BINARY_SENSOR platform."""
    isy_data = make_isy_data()

    climate_type = next(iter(NODE_FILTERS[Platform.CLIMATE][FILTER_INSTEON_TYPE]), None)
    if climate_type is None:
        pytest.skip("No climate insteon type in filters")
    node = make_node(
        protocol=PROTO_INSTEON,
        address=f"1 {SUBNODE_CLIMATE_COOL:X}",
        node_type=climate_type,
    )
    result = _check_for_insteon_type(isy_data, node, single_platform=Platform.CLIMATE)
    assert result is True
    assert node in isy_data.nodes[Platform.BINARY_SENSOR]


def test_check_for_insteon_type_iolinc_relay_redirected_to_switch() -> None:
    """IOLinc relay subnode is placed on SWITCH platform instead of BINARY_SENSOR."""
    isy_data = make_isy_data()
    node = make_node(
        protocol=PROTO_INSTEON,
        address=f"1 {SUBNODE_IOLINC_RELAY:X}",
        node_type="7.0.",
    )
    result = _check_for_insteon_type(
        isy_data, node, single_platform=Platform.BINARY_SENSOR
    )
    assert result is True
    assert node in isy_data.nodes[Platform.SWITCH]


# ---------------------------------------------------------------------------
# _check_for_zwave_cat
# ---------------------------------------------------------------------------


def test_check_for_zwave_cat_non_zwave() -> None:
    """Non-Z-Wave protocol returns False."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_INSTEON)
    assert _check_for_zwave_cat(isy_data, node) is False


def test_check_for_zwave_cat_no_zwave_props() -> None:
    """Z-Wave node without zwave_props returns False."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_ZWAVE)
    del node.zwave_props
    assert _check_for_zwave_cat(isy_data, node) is False


def test_check_for_zwave_cat_none_zwave_props() -> None:
    """Z-Wave node with zwave_props=None returns False."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_ZWAVE)
    node.zwave_props = None
    assert _check_for_zwave_cat(isy_data, node) is False


def test_check_for_zwave_cat_lock_match() -> None:
    """Z-Wave lock category is placed on LOCK platform."""

    lock_cat = next(iter(NODE_FILTERS[Platform.LOCK][FILTER_ZWAVE_CAT]))
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_ZWAVE)
    node.zwave_props = MagicMock(spec=ZWaveProperties)
    node.zwave_props.category = lock_cat
    result = _check_for_zwave_cat(isy_data, node, single_platform=Platform.LOCK)
    assert result is True
    assert node in isy_data.nodes[Platform.LOCK]


def test_check_for_zwave_cat_no_match() -> None:
    """Z-Wave node with unknown category returns False."""
    isy_data = make_isy_data()
    node = make_node(protocol=PROTO_ZWAVE)
    node.zwave_props = MagicMock(spec=ZWaveProperties)
    node.zwave_props.category = "999"
    assert _check_for_zwave_cat(isy_data, node) is False


# ---------------------------------------------------------------------------
# _check_for_uom_id
# ---------------------------------------------------------------------------


def test_check_for_uom_id_no_uom_attr() -> None:
    """Node without uom attr returns False."""
    isy_data = make_isy_data()
    node = make_node()
    del node.uom
    assert _check_for_uom_id(isy_data, node) is False


def test_check_for_uom_id_none_uom() -> None:
    """Node with uom=None returns False."""
    isy_data = make_isy_data()
    node = make_node()
    node.uom = None
    assert _check_for_uom_id(isy_data, node) is False


def test_check_for_uom_id_climate_uom() -> None:
    """Node with climate UOM is placed on CLIMATE platform."""

    climate_uom = next(iter(NODE_FILTERS[Platform.CLIMATE][FILTER_UOM]))
    isy_data = make_isy_data()
    node = make_node()
    node.uom = climate_uom
    result = _check_for_uom_id(isy_data, node, single_platform=Platform.CLIMATE)
    assert result is True
    assert node in isy_data.nodes[Platform.CLIMATE]


def test_check_for_uom_id_with_uom_list() -> None:
    """With uom_list override, only list membership matters."""
    isy_data = make_isy_data()
    node = make_node()
    node.uom = "2"  # binary sensor UOM
    result = _check_for_uom_id(
        isy_data, node, single_platform=Platform.BINARY_SENSOR, uom_list=["2", "78"]
    )
    assert result is True
    assert node in isy_data.nodes[Platform.BINARY_SENSOR]


def test_check_for_uom_id_list_uom_uses_first() -> None:
    """ISYv4 list uom uses first element."""
    lock_uom = next(iter(NODE_FILTERS[Platform.LOCK][FILTER_UOM]))
    isy_data = make_isy_data()
    node = make_node()
    node.uom = [lock_uom, "other"]
    result = _check_for_uom_id(isy_data, node)
    assert result is True
    assert node in isy_data.nodes[Platform.LOCK]


# ---------------------------------------------------------------------------
# _check_for_states_in_uom
# ---------------------------------------------------------------------------


def test_check_for_states_in_uom_non_list_uom() -> None:
    """Non-list uom returns False (ISYv5+ firmware)."""
    isy_data = make_isy_data()
    node = make_node()
    node.uom = "2"
    assert _check_for_states_in_uom(isy_data, node) is False


def test_check_for_states_in_uom_no_uom_attr() -> None:
    """Node without uom returns False."""
    isy_data = make_isy_data()
    node = make_node()
    del node.uom
    assert _check_for_states_in_uom(isy_data, node) is False


def test_check_for_states_in_uom_binary_sensor_states() -> None:
    """List uom matching on/off states is placed on BINARY_SENSOR."""
    isy_data = make_isy_data()
    node = make_node()
    node.uom = ["On", "Off"]
    result = _check_for_states_in_uom(
        isy_data,
        node,
        single_platform=Platform.BINARY_SENSOR,
        states_list=["on", "off"],
    )
    assert result is True
    assert node in isy_data.nodes[Platform.BINARY_SENSOR]


def test_check_for_states_in_uom_no_match() -> None:
    """Unrecognized states list returns False."""
    isy_data = make_isy_data()
    node = make_node()
    node.uom = ["fast", "slow"]
    assert _check_for_states_in_uom(isy_data, node) is False


# ---------------------------------------------------------------------------
# _add_backlight_if_supported
# ---------------------------------------------------------------------------


def test_add_backlight_not_supported() -> None:
    """Node without backlight support is not added to aux_properties."""
    isy_data = make_isy_data()
    node = make_node()
    node.is_backlight_supported = False
    _add_backlight_if_supported(isy_data, node)
    for props in isy_data.aux_properties.values():
        assert not any(n is node for n, _ in props)


def test_add_backlight_uom_index_goes_to_select() -> None:
    """Backlight node_def with UOM_INDEX is added to SELECT aux_properties."""

    isy_data = make_isy_data()
    node = make_node()
    node.is_backlight_supported = True
    # Find a node_def_id whose BACKLIGHT_SUPPORT value == UOM_INDEX
    node_def_for_index = next(k for k, v in BACKLIGHT_SUPPORT.items() if v == UOM_INDEX)
    node.node_def_id = node_def_for_index
    _add_backlight_if_supported(isy_data, node)
    assert any(
        n is node and c == CMD_BACKLIGHT
        for n, c in isy_data.aux_properties[Platform.SELECT]
    )


def test_add_backlight_non_uom_index_goes_to_number() -> None:
    """Backlight node_def without UOM_INDEX is added to NUMBER aux_properties."""

    isy_data = make_isy_data()
    node = make_node()
    node.is_backlight_supported = True
    # Find a node_def_id whose BACKLIGHT_SUPPORT value != UOM_INDEX
    node_def_for_pct = next(k for k, v in BACKLIGHT_SUPPORT.items() if v != UOM_INDEX)
    node.node_def_id = node_def_for_pct
    _add_backlight_if_supported(isy_data, node)
    assert any(
        n is node and c == CMD_BACKLIGHT
        for n, c in isy_data.aux_properties[Platform.NUMBER]
    )


# ---------------------------------------------------------------------------
# _generate_device_info
# ---------------------------------------------------------------------------


def test_generate_device_info_basic() -> None:
    """DeviceInfo includes identifiers, manufacturer, and name from node."""
    node = make_node(protocol=PROTO_INSTEON, address="1 1")
    node.isy = MagicMock()
    node.isy.uuid = "test-uuid"
    node.isy.conn = MagicMock()
    node.isy.conn.url = "http://192.168.1.1"
    node.name = "My Light"
    node.folder = "Bedroom"
    node.node_def_id = "DimmerLampSwitch"
    node.type = "1.32."
    node.zwave_props = None

    device_info = _generate_device_info(node)

    assert ("isy994", "test-uuid_1 1") in device_info["identifiers"]
    assert device_info["name"] == "My Light"
    assert device_info["suggested_area"] == "Bedroom"


def test_generate_device_info_zwave_with_mfr_id() -> None:
    """Z-Wave node with non-zero mfr_id gets extended manufacturer/model info."""

    node = make_node(protocol=PROTO_ZWAVE, address="ZW001")
    node.isy = MagicMock()
    node.isy.uuid = "zw-uuid"
    node.isy.conn = MagicMock()
    node.isy.conn.url = "http://192.168.1.2"
    node.name = "Z-Wave Switch"
    node.folder = None
    node.node_def_id = None
    node.type = None
    node.zwave_props = MagicMock(spec=ZWaveProperties)
    node.zwave_props.mfr_id = "256"
    node.zwave_props.prod_type_id = "1"
    node.zwave_props.product_id = "2"

    device_info = _generate_device_info(node)

    assert ATTR_MANUFACTURER in device_info
    assert "Z-Wave MfrID" in device_info[ATTR_MANUFACTURER]
    assert ATTR_MODEL in device_info


def test_generate_device_info_zwave_zero_mfr_id() -> None:
    """Z-Wave node with mfr_id '0' does not override manufacturer."""

    node = make_node(protocol=PROTO_ZWAVE, address="ZW002")
    node.isy = MagicMock()
    node.isy.uuid = "zw-uuid2"
    node.isy.conn = MagicMock()
    node.isy.conn.url = "http://192.168.1.3"
    node.name = "Generic Z-Wave"
    node.folder = None
    node.node_def_id = None
    node.type = None
    node.zwave_props = MagicMock(spec=ZWaveProperties)
    node.zwave_props.mfr_id = "0"

    device_info = _generate_device_info(node)

    # manufacturer key should not appear (or be the protocol title if not Z-Wave mfr)
    assert ATTR_MANUFACTURER not in device_info or "Z-Wave MfrID" not in str(
        device_info.get(ATTR_MANUFACTURER, "")
    )
