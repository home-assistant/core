"""Tests for Panasonic Viera PAC picture mode selection."""

from unittest.mock import Mock, patch

from panasonic_viera import SOAPError

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.panasonic_viera.const import ATTR_UDN, DOMAIN
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_OPTION
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_INFO,
    MOCK_ENCRYPTION_DATA,
    get_mock_remote,
)

from tests.common import MockConfigEntry


async def test_picture_mode_select(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test PAC picture modes are exposed as a select entity."""
    state = hass.states.get("select.panasonic_viera_tv_picture_mode")
    assert state.state == "Normal"
    assert state.attributes["options"] == ["Normal", "Cinema", "Game"]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {"entity_id": state.entity_id, ATTR_OPTION: "Cinema"},
        blocking=True,
    )
    mock_remote.set_picture_mode.assert_called_once_with("Cinema")


async def test_no_picture_mode_select_without_pac(hass: HomeAssistant) -> None:
    """Test PAC entities are not added for televisions without PAC support."""
    mock_remote = get_mock_remote()
    mock_remote.list_inputs.side_effect = SOAPError("unsupported")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA, **MOCK_DEVICE_INFO},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("select.panasonic_viera_tv_picture_mode") is None
    state = hass.states.get("media_player.panasonic_viera_tv")
    assert (
        not state.attributes["supported_features"]
        & MediaPlayerEntityFeature.SELECT_SOURCE
    )
