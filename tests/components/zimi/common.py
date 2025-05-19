"""Common items for testing the zimi component."""

from unittest.mock import MagicMock, patch

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


def mock_entity(
    device_name: str | None = None, entity_type: str | None = None
) -> MagicMock:
    """Mock a Zimi entity with defaults."""

    mock_entity = MagicMock()

    mock_entity.identifier = ENTITY_INFO["id"]
    mock_entity.room = ENTITY_INFO["room"]
    mock_entity.name = ENTITY_INFO["name"]
    mock_entity.type = entity_type or ENTITY_INFO["type"]

    mock_manfacture_info = MagicMock()
    mock_manfacture_info.identifier = DEVICE_INFO["id"]
    mock_manfacture_info.manufacturer = DEVICE_INFO["manufacturer"]
    mock_manfacture_info.model = DEVICE_INFO["model"]
    mock_manfacture_info.name = device_name or DEVICE_INFO["name"]
    mock_manfacture_info.hwVersion = DEVICE_INFO["hwVersion"]
    mock_manfacture_info.firmwareVersion = DEVICE_INFO["fwVersion"]

    mock_entity.manufacture_info = mock_manfacture_info

    return mock_entity


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
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
