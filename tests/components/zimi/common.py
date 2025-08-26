"""Common items for testing the zimi component."""

from unittest.mock import MagicMock, create_autospec, patch

from zcc.device import ControlPointDevice

from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

DEVICE_INFO = {
    "id": "test-device-id",
    "name": "unknown",
    "manufacturer": "Zimi",
    "model": "Controller XYZ",
    "hwVersion": "2.2.2",
    "fwVersion": "3.3.3",
}

ENTITY_INFO = {
    "id": "test-entity-id",
    "name": "Test Entity Name",
    "room": "Test Entity Room",
    "type": "unknown",
}

INPUT_HOST = "192.168.1.100"
INPUT_PORT = 5003


def mock_api_device(
    device_name: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> MagicMock:
    """Mock a Zimi ControlPointDevice which is used in the zcc API with defaults."""

    mock_api_device = create_autospec(ControlPointDevice)

    mock_api_device.identifier = entity_id or ENTITY_INFO["id"]
    mock_api_device.room = ENTITY_INFO["room"]
    mock_api_device.name = ENTITY_INFO["name"]
    mock_api_device.type = entity_type or ENTITY_INFO["type"]

    mock_manfacture_info = MagicMock()
    mock_manfacture_info.identifier = DEVICE_INFO["id"]
    mock_manfacture_info.manufacturer = DEVICE_INFO["manufacturer"]
    mock_manfacture_info.model = DEVICE_INFO["model"]
    mock_manfacture_info.name = device_name or DEVICE_INFO["name"]
    mock_manfacture_info.hwVersion = DEVICE_INFO["hwVersion"]
    mock_manfacture_info.firmwareVersion = DEVICE_INFO["fwVersion"]

    mock_api_device.manufacture_info = mock_manfacture_info

    mock_api_device.brightness = 0
    mock_api_device.percentage = 0

    return mock_api_device


async def setup_platform(
    hass: HomeAssistant,
    platform: str,
) -> MockConfigEntry:
    """Set up the specified Zimi platform."""

    if not platform:
        raise ValueError("Platform must be specified")

    mock_config = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: INPUT_HOST, CONF_PORT: INPUT_PORT}
    )
    mock_config.add_to_hass(hass)

    with patch("homeassistant.components.zimi.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return mock_config
