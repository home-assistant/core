"""Test LIFX diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components import lifx
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    SERIAL,
    MockLifxCommand,
    _mocked_128zone_ceiling,
    _mocked_bulb,
    _mocked_ceiling,
    _mocked_clean_bulb,
    _mocked_infrared_bulb,
    _mocked_light_strip,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_bulb_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot


async def test_clean_bulb_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_clean_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot


async def test_infrared_bulb_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot


async def test_legacy_multizone_bulb_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.get_color_zones = MockLifxCommand(
        bulb,
        msg_seq_num=0,
        msg_count=8,
        msg_color=[
            (54612, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
        ],
        msg_index=0,
    )
    bulb.zones_count = 8
    bulb.color_zones = [
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot


async def test_multizone_bulb_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.product = 38
    bulb.get_color_zones = MockLifxCommand(
        bulb,
        msg_seq_num=0,
        msg_count=8,
        msg_color=[
            (54612, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
            (46420, 65535, 65535, 3500),
        ],
        msg_index=0,
    )
    bulb.zones_count = 8
    bulb.color_zones = [
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot


async def test_matrix_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_ceiling()
    bulb.effect = {"effect": "OFF"}
    bulb.tile_devices_count = 1
    bulb.tile_device_width = 8
    bulb.tile_devices = [
        {
            "accel_meas_x": 0,
            "accel_meas_y": 0,
            "accel_meas_z": 2000,
            "user_x": 0.0,
            "user_y": 0.0,
            "width": 8,
            "height": 8,
            "supported_frame_buffers": 5,
            "device_version_vendor": 1,
            "device_version_product": 176,
            "firmware_build": 1729829374000000000,
            "firmware_version_minor": 10,
            "firmware_version_major": 4,
        }
    ]
    bulb.chain = {0: [(0, 0, 0, 3500)] * 64}
    bulb.chain_length = 1

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot


async def test_128zone_matrix_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_128zone_ceiling()
    bulb.effect = {"effect": "OFF"}
    bulb.tile_devices_count = 1
    bulb.tile_device_width = 16
    bulb.tile_devices = [
        {
            "accel_meas_x": 0,
            "accel_meas_y": 0,
            "accel_meas_z": 2000,
            "user_x": 0.0,
            "user_y": 0.0,
            "width": 8,
            "height": 16,
            "supported_frame_buffers": 5,
            "device_version_vendor": 1,
            "device_version_product": 201,
            "firmware_build": 1729829374000000000,
            "firmware_version_minor": 10,
            "firmware_version_major": 4,
        }
    ]
    bulb.chain = {0: [(0, 0, 0, 3500)] * 128}
    bulb.chain_length = 1

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == snapshot
