"""Huawei LTE component tests."""
from unittest.mock import Mock

import pytest

from homeassistant.components import huawei_lte
from homeassistant.components.huawei_lte.const import KEY_DEVICE_INFORMATION


@pytest.fixture(autouse=True)
def routerdata():
    """Set up a router data for testing."""
    rd = huawei_lte.RouterData(Mock(), "de:ad:be:ef:00:00")
    rd.device_information = {"SoftwareVersion": "1.0", "nested": {"foo": "bar"}}
    return rd


async def test_routerdata_get_nonexistent_root(routerdata):
    """Test that accessing a nonexistent root element raises KeyError."""
    with pytest.raises(KeyError):  # NOT AttributeError
        routerdata["nonexistent_root.foo"]


async def test_routerdata_get_nonexistent_leaf(routerdata):
    """Test that accessing a nonexistent leaf element raises KeyError."""
    with pytest.raises(KeyError):
        routerdata[f"{KEY_DEVICE_INFORMATION}.foo"]


async def test_routerdata_get_nonexistent_leaf_path(routerdata):
    """Test that accessing a nonexistent long path raises KeyError."""
    with pytest.raises(KeyError):
        routerdata[f"{KEY_DEVICE_INFORMATION}.long.path.foo"]


async def test_routerdata_get_simple(routerdata):
    """Test that accessing a short, simple path works."""
    assert routerdata[f"{KEY_DEVICE_INFORMATION}.SoftwareVersion"] == "1.0"


async def test_routerdata_get_longer(routerdata):
    """Test that accessing a longer path works."""
    assert routerdata[f"{KEY_DEVICE_INFORMATION}.nested.foo"] == "bar"


async def test_routerdata_get_dict(routerdata):
    """Test that returning an intermediate dict works."""
    assert routerdata[f"{KEY_DEVICE_INFORMATION}.nested"] == {"foo": "bar"}
