"""Common items for testing the zimi component."""

from unittest.mock import AsyncMock, MagicMock, patch

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


async def check_states(
    hass: HomeAssistant,
    entity_type: str,
    entity_key: str,
) -> None:
    """Check that the entity states exist."""

    state = hass.states.get(entity_key)
    assert state is not None
    assert state.entity_id == entity_key


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

    assert "turn_on" in services[entity_type_override or entity_type]

    await hass.services.async_call(
        entity_type_override or entity_type,
        "turn_on",
        {"entity_id": entity_key},
        blocking=True,
    )

    if turn_on_override:
        assert turn_on_override.called
    else:
        assert mock_device.turn_on.called

    assert "turn_off" in services[entity_type_override or entity_type]

    await hass.services.async_call(
        entity_type_override or entity_type,
        "turn_off",
        {"entity_id": entity_key},
        blocking=True,
    )

    if turn_off_override:
        assert turn_off_override.called
    else:
        assert mock_device.turn_off.called


def mock_entity(
    device_name: str | None = None,
    entity_type: str | None = None,
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

    mock_entity.subscribe = AsyncMock()

    mock_entity.close_door = AsyncMock()
    mock_entity.open_door = AsyncMock()
    mock_entity.open_to_percentage = AsyncMock()
    mock_entity.set_brightness = AsyncMock()
    mock_entity.set_fanspeed = AsyncMock()
    mock_entity.turn_on = AsyncMock()
    mock_entity.turn_off = AsyncMock()

    return mock_entity


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
