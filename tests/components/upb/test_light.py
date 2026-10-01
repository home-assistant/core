"""The light tests for the UPB platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from upb_lib.devices import UpbAddr, UpbDevice

from homeassistant.components.upb.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_FILE_PATH,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

LIGHT_ENTITY_ID = "light.test_light"


@pytest.fixture
def mock_upb_device() -> UpbDevice:
    """Return a UPB device element."""
    device = UpbDevice(UpbAddr(1, 2, 0), MagicMock())
    device.name = "Test light"
    device.status = 0
    device.dimmable = True
    # Spy on the public callback API while keeping the real behavior.
    device.add_callback = MagicMock(wraps=device.add_callback)
    device.remove_callback = MagicMock(wraps=device.remove_callback)
    return device


@pytest.fixture
def mock_upb(mock_upb_device: UpbDevice) -> Generator[MagicMock]:
    """Mock the UPB PIM with a single device."""
    with (
        patch("homeassistant.components.upb.PLATFORMS", [Platform.LIGHT]),
        patch("homeassistant.components.upb.upb_lib.UpbPim") as mock_pim_cls,
    ):
        upb = mock_pim_cls.return_value
        upb.load_upstart_file = AsyncMock()
        upb.async_connect = AsyncMock()
        upb.is_connected.return_value = True
        upb.devices = {mock_upb_device.index: mock_upb_device}
        upb.links = {}
        yield upb


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the UPB integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "tcp://1.2.3.4", CONF_FILE_PATH: "upb.upe"},
        version=1,
        minor_version=3,
        unique_id="42",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("mock_upb")
async def test_element_callback_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_upb_device: UpbDevice,
) -> None:
    """Test removing the entity removes its element callback."""
    await setup_integration(hass)
    assert hass.states.get(LIGHT_ENTITY_ID)
    mock_upb_device.add_callback.assert_called_once()
    mock_upb_device.remove_callback.assert_not_called()
    element_callback = mock_upb_device.add_callback.call_args.args[0]

    entity_registry.async_remove(LIGHT_ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(LIGHT_ENTITY_ID) is None
    mock_upb_device.remove_callback.assert_called_once_with(element_callback)


@pytest.mark.usefixtures("mock_upb")
async def test_element_callback_not_duplicated_on_readd(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_upb_device: UpbDevice,
) -> None:
    """Test re-adding the entity does not leave a stale element callback."""
    await setup_integration(hass)
    element_callback = mock_upb_device.add_callback.call_args.args[0]

    # Changing the entity_id removes and re-adds the same entity object.
    entity_registry.async_update_entity(
        LIGHT_ENTITY_ID, new_entity_id="light.renamed_light"
    )
    await hass.async_block_till_done()

    assert mock_upb_device.add_callback.call_count == 2
    mock_upb_device.remove_callback.assert_called_once_with(element_callback)

    assert hass.states.get("light.renamed_light").state == STATE_OFF
    # The element still notifies the re-added entity.
    mock_upb_device.setattr("status", 100)
    assert hass.states.get("light.renamed_light").state == STATE_ON
