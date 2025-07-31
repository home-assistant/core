import pytest

from homeassistant.components.rexense.config_flow import RexenseConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from voluptuous import Schema


def test_config_flow_class_exists():
    assert hasattr(RexenseConfigFlow, 'async_step_user')
    assert hasattr(RexenseConfigFlow, 'async_step_zeroconf')
