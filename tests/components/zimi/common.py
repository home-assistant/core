"""Common items for testing the zimi component."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, SERVICE_TURN_OFF, SERVICE_TURN_ON
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


async def check_toggle(
    hass: HomeAssistant,
    entity_type: str,
    entity_key: str,
    mock_device: MagicMock,
    entity_type_override: str | None = None,
    turn_on_override: AsyncMock | None = None,
    turn_off_override: AsyncMock | None = None,
) -> None:
    """Check that the entity can be toggled on and off.

    Allows for override of default entity_type and turn_on and turn_off.
    """

    services = hass.services.async_services()

    assert SERVICE_TURN_ON in services[entity_type_override or entity_type]

    await hass.services.async_call(
        entity_type_override or entity_type,
        SERVICE_TURN_ON,
        {"entity_id": entity_key},
        blocking=True,
    )

    if turn_on_override:
        assert turn_on_override.called
    else:
        assert mock_device.turn_on.called

    assert SERVICE_TURN_OFF in services[entity_type_override or entity_type]

    await hass.services.async_call(
        entity_type_override or entity_type,
        SERVICE_TURN_OFF,
        {"entity_id": entity_key},
        blocking=True,
    )

    if turn_off_override:
        assert turn_off_override.called
    else:
        assert mock_device.turn_off.called


def mock_api_device(
    device_name: str | None = None,
    entity_type: str | None = None,
) -> MagicMock:
    """Mock a Zimi ControlPointDevice which is used in the zcc API with defaults."""

    mock_api_device = MagicMock()

    mock_api_device.identifier = ENTITY_INFO["id"]
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

    mock_api_device.subscribe = AsyncMock()

    mock_api_device.brightness = 0
    mock_api_device.percentage = 0

    mock_api_device.close_door = AsyncMock()
    mock_api_device.open_door = AsyncMock()
    mock_api_device.open_to_percentage = AsyncMock()

    mock_api_device.set_brightness = AsyncMock()
    mock_api_device.set_fanspeed = AsyncMock()
    mock_api_device.turn_on = AsyncMock()
    mock_api_device.turn_off = AsyncMock()

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
