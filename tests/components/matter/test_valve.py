"""Test Matter valve."""

from math import floor
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
import pytest

from homeassistant.components.cover import (
    STATE_CLOSED,
    STATE_OPEN,
    STATE_OPENING,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)
