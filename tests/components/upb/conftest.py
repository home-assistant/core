"""Tests for the UPB component."""
import pytest
from upb_lib.links import Link, LinkAddr

from homeassistant.components.upb.scene import UpbLink

from tests.async_mock import Mock


@pytest.fixture(name="element")
def element_fixture():
    """Create UPB element fixture."""
    element = Mock(Link)
    element.addr = LinkAddr(42, 24)
    return element


@pytest.fixture(name="upb_link")
def upb_entity_fixture(hass, element):
    """Get a mocked UPB scene."""
    link = UpbLink(element, "soft_kitty", None)
    link.hass = hass
    return link
