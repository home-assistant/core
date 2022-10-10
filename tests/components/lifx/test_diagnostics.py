"""Test LIFX diagnostics."""
from homeassistant.components import lifx
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_bulb,
    _mocked_clean_bulb,
    _mocked_infrared_bulb,
    _mocked_light_strip,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_bulb_diagnostics(hass: HomeAssistant, hass_client) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == {
        "data": {
            "features": {
                "buttons": False,
                "chain": False,
                "color": True,
                "extended_multizone": False,
                "hev": False,
                "infrared": False,
                "matrix": False,
                "max_kelvin": 9000,
                "min_kelvin": 2500,
                "multizone": False,
                "relays": False,
            },
            "firmware": "3.00",
            "state": {
                "brightness": 0.0,
                "hue": 0.01,
                "kelvin": 4,
                "power": "off",
                "saturation": 0.0,
            },
            "version": {"product_id": 1, "vendor": None},
        },
        "entry": {"data": {"host": "**REDACTED**"}, "title": "My Bulb"},
    }


async def test_clean_bulb_diagnostics(hass: HomeAssistant, hass_client) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_clean_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == {
        "data": {
            "features": {
                "buttons": False,
                "chain": False,
                "color": True,
                "extended_multizone": False,
                "hev": True,
                "infrared": False,
                "matrix": False,
                "max_kelvin": 9000,
                "min_kelvin": 1500,
                "multizone": False,
                "relays": False,
            },
            "firmware": "3.00",
            "hev": {
                "hev_config": {"duration": 7200, "indication": False},
                "hev_cycle": {"duration": 7200, "last_power": False, "remaining": 30},
                "last_result": 0,
            },
            "state": {
                "brightness": 0.0,
                "hue": 0.01,
                "kelvin": 4,
                "power": "off",
                "saturation": 0.0,
            },
            "version": {"product_id": 90, "vendor": None},
        },
        "entry": {"data": {"host": "**REDACTED**"}, "title": "My Bulb"},
    }


async def test_infrared_bulb_diagnostics(hass: HomeAssistant, hass_client) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == {
        "data": {
            "features": {
                "buttons": False,
                "chain": False,
                "color": True,
                "extended_multizone": False,
                "hev": False,
                "infrared": True,
                "matrix": False,
                "max_kelvin": 9000,
                "min_kelvin": 1500,
                "multizone": False,
                "relays": False,
            },
            "firmware": "3.00",
            "infrared": {"brightness": 65535},
            "state": {
                "brightness": 0.0,
                "hue": 0.01,
                "kelvin": 4,
                "power": "off",
                "saturation": 0.0,
            },
            "version": {"product_id": 29, "vendor": None},
        },
        "entry": {"data": {"host": "**REDACTED**"}, "title": "My Bulb"},
    }


async def test_legacy_multizone_bulb_diagnostics(
    hass: HomeAssistant, hass_client
) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
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
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == {
        "data": {
            "features": {
                "buttons": False,
                "chain": False,
                "color": True,
                "extended_multizone": False,
                "hev": False,
                "infrared": False,
                "matrix": False,
                "max_kelvin": 9000,
                "min_kelvin": 2500,
                "multizone": True,
                "relays": False,
            },
            "firmware": "3.00",
            "state": {
                "brightness": 0.0,
                "hue": 0.01,
                "kelvin": 4,
                "power": "off",
                "saturation": 0.0,
            },
            "version": {"product_id": 31, "vendor": None},
            "zones": {
                "count": 8,
                "state": {
                    "0": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "1": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "2": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "3": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "4": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "5": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "6": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "7": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                },
            },
        },
        "entry": {"data": {"host": "**REDACTED**"}, "title": "My Bulb"},
    }


async def test_multizone_bulb_diagnostics(hass: HomeAssistant, hass_client) -> None:
    """Test diagnostics for a standard bulb."""
    config_entry = MockConfigEntry(
        domain=lifx.DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.product = 38
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
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == {
        "data": {
            "features": {
                "buttons": False,
                "chain": False,
                "color": True,
                "extended_multizone": True,
                "hev": False,
                "infrared": False,
                "matrix": False,
                "max_kelvin": 9000,
                "min_ext_mz_firmware": 1532997580,
                "min_ext_mz_firmware_components": [2, 77],
                "min_kelvin": 1500,
                "multizone": True,
                "relays": False,
            },
            "firmware": "3.00",
            "state": {
                "brightness": 0.0,
                "hue": 0.01,
                "kelvin": 4,
                "power": "off",
                "saturation": 0.0,
            },
            "version": {"product_id": 38, "vendor": None},
            "zones": {
                "count": 8,
                "state": {
                    "0": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "1": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "2": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "3": {
                        "brightness": 100.0,
                        "hue": 300.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "4": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "5": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "6": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                    "7": {
                        "brightness": 100.0,
                        "hue": 255.0,
                        "kelvin": 3500,
                        "saturation": 100.0,
                    },
                },
            },
        },
        "entry": {"data": {"host": "**REDACTED**"}, "title": "My Bulb"},
    }
