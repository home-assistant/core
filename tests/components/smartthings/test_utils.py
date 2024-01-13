"""Tests for the utils module."""
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from pysmartthings import CAPABILITIES, AppEntity, Capability, Attribute
import pytest

from homeassistant.components.smartthings import utils
from homeassistant.components.smartthings.const import (
    CONF_REFRESH_TOKEN,
    DATA_MANAGER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_format_component_name_with_component_id(hass: HomeAssistant, app) -> None:
    """Test format component name with component id."""
    # Act
    text = utils.format_component_name("test", "test", "test")

    # Assert
    assert text == "test test test"


async def test_format_component_name_without_component_id(hass: HomeAssistant, app) -> None:
    """Test format component name without component id."""
    # Act
    text = utils.format_component_name("test", "test", None)

    # Assert
    assert text == "test test"


async def get_device_status_with_component_id(
    hass: HomeAssistant, smartthings_mock, location, device_factory
) -> None:
    """Test the utils get device status with component id."""
    # Arrange
    device = {
        "status": {
            "secondary": {
                "status": "test"
            }
        }
    }

    # Act
    device_status = utils.get_device_status(device, "secondary")
    # Assert
    assert device_status == "test"


async def get_device_status_without_component_id(
    hass: HomeAssistant, smartthings_mock, location, device_factory
) -> None:
    """Test the utils get device status without component id."""
    # Arrange
    device = {
        "status": "test"
    }

    # Act
    device_status = utils.get_device_status(device, None)
    # Assert
    assert device_status == "test"


async def get_device_attributes_single_components(device_factory) -> None:
    """Test the utils get device attribute with single component."""
    device = device_factory(
        "Color Dimmer 1",
        capabilities=[Capability.switch, Capability.switch_level],
        status={Attribute.switch: "on", Attribute.level: 100},
    )

    # Act
    device_status = utils.get_device_attributes(device)
    # Assert
    assert device_status is not None


async def get_device_attributes_multiple_components(device_factory) -> None:
    """Test the utils get device attribute with multiple component."""
    device = device_factory(
        "Dimmer 1",
        capabilities=[Capability.switch, Capability.switch_level],
        status={Attribute.switch: "on", Attribute.level: 100},
    )

    # Act
    device_status = utils.get_device_attributes(device)
    # Assert
    assert device_status is not None


async def get_device_attr_multiple_components_and_disabled_components(device_factory) -> None:
    """Test the utils get device attribute with multiple component with disabled components."""
    device = device_factory(
        "Dimmer 1",
        capabilities=[Capability.switch, Capability.switch_level],
        status={Attribute.switch: "on", Attribute.level: 100, "disabledComponents": ["with_unsupported_capabilities"]},
    )

    # Act
    device_status = utils.get_device_attributes(device)
    # Assert
    assert device_status is not None
