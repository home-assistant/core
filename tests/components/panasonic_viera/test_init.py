"""Test the Panasonic Viera setup process."""

from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.panasonic_viera.const import (
    ATTR_DEVICE_INFO,
    ATTR_UDN,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_INFO,
    MOCK_ENCRYPTION_DATA,
    MOCK_MAC,
    MOCK_UDN,
    get_mock_remote,
)


async def test_setup_entry_encrypted(hass: HomeAssistant, mock_remote) -> None:
    """Test setup with encrypted config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    state_remote = hass.states.get("remote.panasonic_viera_tv")

    assert state_tv
    assert state_tv.name == DEFAULT_NAME

    assert state_remote
    assert state_remote.name == DEFAULT_NAME


async def test_setup_entry_encrypted_missing_device_info(
    hass: HomeAssistant, mock_remote
) -> None:
    """Test setup with encrypted config entry and missing device info."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.data[ATTR_DEVICE_INFO] == MOCK_DEVICE_INFO
    assert mock_entry.unique_id == MOCK_DEVICE_INFO[ATTR_UDN]

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    state_remote = hass.states.get("remote.panasonic_viera_tv")

    assert state_tv
    assert state_tv.name == DEFAULT_NAME

    assert state_remote
    assert state_remote.name == DEFAULT_NAME


async def test_setup_entry_encrypted_missing_device_info_none(
    hass: HomeAssistant,
) -> None:
    """Test setup with encrypted config entry and device info set to None."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote(device_info=None)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.data[ATTR_DEVICE_INFO] is None
        assert mock_entry.unique_id == MOCK_CONFIG_DATA[CONF_HOST]

        state_tv = hass.states.get("media_player.panasonic_viera_tv")
        state_remote = hass.states.get("remote.panasonic_viera_tv")

        assert state_tv
        assert state_tv.name == DEFAULT_NAME

        assert state_remote
        assert state_remote.name == DEFAULT_NAME


async def test_setup_entry_unencrypted(hass: HomeAssistant, mock_remote) -> None:
    """Test setup with unencrypted config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    state_remote = hass.states.get("remote.panasonic_viera_tv")

    assert state_tv
    assert state_tv.name == DEFAULT_NAME

    assert state_remote
    assert state_remote.name == DEFAULT_NAME


async def test_setup_entry_unencrypted_missing_device_info(
    hass: HomeAssistant, mock_remote
) -> None:
    """Test setup with unencrypted config entry and missing device info."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.data[ATTR_DEVICE_INFO] == MOCK_DEVICE_INFO
    assert mock_entry.unique_id == MOCK_DEVICE_INFO[ATTR_UDN]

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    state_remote = hass.states.get("remote.panasonic_viera_tv")

    assert state_tv
    assert state_tv.name == DEFAULT_NAME

    assert state_remote
    assert state_remote.name == DEFAULT_NAME


async def test_setup_entry_unencrypted_missing_device_info_none(
    hass: HomeAssistant,
) -> None:
    """Test setup with unencrypted config entry and device info set to None."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote(device_info=None)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.data[ATTR_DEVICE_INFO] is None
        assert mock_entry.unique_id == MOCK_CONFIG_DATA[CONF_HOST]

        state_tv = hass.states.get("media_player.panasonic_viera_tv")
        state_remote = hass.states.get("remote.panasonic_viera_tv")

        assert state_tv
        assert state_tv.name == DEFAULT_NAME

        assert state_remote
        assert state_remote.name == DEFAULT_NAME


async def test_setup_config_flow_initiated(hass: HomeAssistant) -> None:
    """Test if config flow is initiated in setup."""
    mock_remote = get_mock_remote()
    mock_remote.get_device_info = Mock(side_effect=OSError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        assert (
            await async_setup_component(
                hass,
                DOMAIN,
                {DOMAIN: {CONF_HOST: "0.0.0.0"}},
            )
            is True
        )

    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_setup_unload_entry(hass: HomeAssistant, mock_remote) -> None:
    """Test if config entry is unloaded."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    state_remote = hass.states.get("remote.panasonic_viera_tv")

    assert state_tv.state == STATE_UNAVAILABLE
    assert state_remote.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(mock_entry.entry_id)
    await hass.async_block_till_done()

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    state_remote = hass.states.get("remote.panasonic_viera_tv")

    assert state_tv is None
    assert state_remote is None


@pytest.mark.parametrize(
    ("udn", "extra_data", "expected_mac", "expected_connections"),
    [
        pytest.param(
            MOCK_UDN,
            {},
            MOCK_MAC,
            {(dr.CONNECTION_NETWORK_MAC, MOCK_MAC)},
            id="mac_in_udn",
        ),
        pytest.param(
            MOCK_UDN,
            {CONF_MAC: "aa:bb:cc:dd:ee:ff"},
            "aa:bb:cc:dd:ee:ff",
            {(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
            id="mac_already_known",
        ),
        pytest.param(
            "uuid:4D454930-0600-1000-8000-FFFFFFFFFFFF",
            {},
            None,
            set(),
            id="random_node",
        ),
        pytest.param(
            "uuid:12345678-1234-4234-8234-123456789abc",
            {},
            None,
            set(),
            id="not_time_based",
        ),
        pytest.param("mock-unique-id", {}, None, set(), id="not_a_uuid"),
    ],
)
@pytest.mark.usefixtures("mock_remote")
async def test_setup_entry_device_connections(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    udn: str,
    extra_data: dict[str, str],
    expected_mac: str | None,
    expected_connections: set[tuple[str, str]],
) -> None:
    """Test the MAC address embedded in the UDN becomes a device connection."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=udn,
        data={
            **MOCK_CONFIG_DATA,
            ATTR_DEVICE_INFO: {**MOCK_DEVICE_INFO, ATTR_UDN: udn},
            **extra_data,
        },
    )
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.data.get(CONF_MAC) == expected_mac
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, udn), mock_entry.entry_id
    )
    assert device is not None
    assert device.connections == expected_connections
