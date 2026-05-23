"""Test ISY994 helpers."""

import logging
from unittest.mock import MagicMock

from pyisy.constants import PROTO_ZWAVE
import pytest

from homeassistant.components.isy994.helpers import _generate_device_info


@pytest.fixture
def zwave_node(mock_isy: MagicMock) -> MagicMock:
    """Return a mock Z-Wave ISY node."""
    node = MagicMock()
    node.isy = mock_isy
    node.address = "ZW001"
    node.name = "Z-Wave Lock"
    node.node_def_id = "ZWaveLock"
    node.type = None
    node.protocol = PROTO_ZWAVE
    node.folder = None
    node.zwave_props = MagicMock()
    node.zwave_props.mfr_id = "99"
    node.zwave_props.prod_type_id = "18756"
    node.zwave_props.product_id = "12593"
    return node


def test_generate_device_info_zwave_numeric_ids(zwave_node: MagicMock) -> None:
    """Test _generate_device_info does not raise with valid numeric Z-Wave IDs."""
    device_info = _generate_device_info(zwave_node)
    assert device_info is not None


@pytest.mark.parametrize(
    ("mfr_id", "prod_type_id", "product_id"),
    [
        pytest.param("N/A", "N/A", "N/A", id="not_applicable"),
        pytest.param("unknown", "0x4944", "0x3131", id="non_numeric_mfr"),
    ],
)
def test_generate_device_info_zwave_non_numeric_ids_logs_warning(
    zwave_node: MagicMock,
    mfr_id: str,
    prod_type_id: str,
    product_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _generate_device_info logs a warning for non-numeric Z-Wave IDs."""
    zwave_node.zwave_props.mfr_id = mfr_id
    zwave_node.zwave_props.prod_type_id = prod_type_id
    zwave_node.zwave_props.product_id = product_id

    with caplog.at_level(logging.WARNING, logger="homeassistant.components.isy994"):
        device_info = _generate_device_info(zwave_node)

    assert device_info is not None
    assert "non-numeric" in caplog.text
