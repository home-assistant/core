"""iNELS light platform testing."""

from unittest.mock import patch

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import MAC_ADDRESS, UNIQUE_ID, get_entity_id

DT_05 = "05"
DT_06 = "06"
DT_13 = "13"
DT_101 = "101"
DT_114 = "114"
DT_153 = "153"


@pytest.fixture(params=["simple_light", "light_coa_toa", "warm_light"])
def entity_config(request: pytest.FixtureRequest):
    """Fixture to provide parameterized entity configuration for light tests."""
    configs = {
        "simple_light": {
            "entity_type": "light",
            "device_type": "simple_light",
            "dev_type": DT_05,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_05}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_05}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_05}/{UNIQUE_ID}",
            "light_off_value": "D8\nEF\n",
            "light_on_value": "8A\nCF\n",
        },
        "light_coa_toa": {
            "entity_type": "light",
            "device_type": "light_coa_toa",
            "dev_type": DT_101,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_101}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_101}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_101}/{UNIQUE_ID}",
            "light_off_value": "7F\nFF\n00\n03\n00\n00\n00\n1D\n00\n00\n",
            "light_on_value": "7F\nFF\n00\n03\n64\n64\n00\n1D\n00\n00\n",
            "alerts": {
                "toa": "7F\nFF\n30\n03\n64\n64\n00\n1D\n00\n00\n",
                "coa": "7F\nFF\nC0\n03\n64\n64\n00\n1D\n00\n00\n",
            },
        },
        "rgb": {
            "entity_type": "light",
            "device_type": "rgb",
            "dev_type": DT_06,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_06}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_06}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_06}/{UNIQUE_ID}",
            "light_off_value": "01\n00\n00\n00\n00\n00\n",
            "light_on_value": "01\nFF\nFF\nFF\nFF\n00\n",
        },
        "rgbw": {
            "entity_type": "light",
            "device_type": "rgbw",
            "dev_type": DT_153,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_153}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_153}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_153}/{UNIQUE_ID}",
            "light_off_value": "00\n00\n00\n00\n00\n00\n00\n00\n0A\n28\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n00\n",
            "light_on_value": "00\n00\n00\n00\n64\n64\n64\n64\n0A\n28\n00\n00\n64\n64\n64\n64\n00\n00\n00\n00\n64\n64\n64\n64\n00\n00\n00\n00\n64\n64\n64\n",
        },
        "warm_light": {
            "entity_type": "light",
            "device_type": "warm_light",
            "dev_type": DT_13,
            "unique_id": UNIQUE_ID,
            "gw_connected_topic": f"inels/connected/{MAC_ADDRESS}/gw",
            "connected_topic": f"inels/connected/{MAC_ADDRESS}/{DT_13}/{UNIQUE_ID}",
            "status_topic": f"inels/status/{MAC_ADDRESS}/{DT_13}/{UNIQUE_ID}",
            "base_topic": f"{MAC_ADDRESS}/{DT_13}/{UNIQUE_ID}",
            "light_off_value": "07\n00\n00\n00\n00\n00\n",
            "light_on_value": "07\n00\n00\n00\nFF\nFF\n",
        },
    }
    return configs[request.param]


@pytest.mark.parametrize(
    ("entity_config", "index"),
    [
        ("simple_light", None),
        ("light_coa_toa", 0),
        ("warm_light", None),
    ],
    indirect=["entity_config"],
)
@pytest.mark.parametrize(
    ("gw_available", "device_available", "expected_state"),
    [
        (True, False, STATE_UNAVAILABLE),
        (False, True, STATE_UNAVAILABLE),
        (True, True, STATE_ON),
    ],
)
async def test_light_availability(
    hass: HomeAssistant,
    setup_entity,
    entity_config,
    index,
    gw_available,
    device_available,
    expected_state,
) -> None:
    """Test light availability and state under different gateway and device availability conditions."""

    light = await setup_entity(
        entity_config,
        status_value=entity_config["light_on_value"],
        gw_available=gw_available,
        device_available=device_available,
        index=index,
    )

    assert light is not None
    assert light.state == expected_state


@pytest.mark.parametrize(
    ("entity_config", "alert_key"),
    [
        ("light_coa_toa", "coa"),
        ("light_coa_toa", "toa"),
    ],
    indirect=["entity_config"],
)
async def test_light_control_with_alerts(
    hass: HomeAssistant,
    setup_entity,
    entity_config,
    alert_key,
) -> None:
    """Test that ServiceValidationError is raised when operating light with active alerts."""
    alert_status_value = entity_config["alerts"][alert_key]

    light = await setup_entity(entity_config, status_value=alert_status_value, index=0)

    assert light is not None

    # Verify that ServiceValidationError is raised when trying to turn on the light
    with pytest.raises(
        ServiceValidationError, match="Cannot operate light with active alerts"
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: get_entity_id(hass, entity_config, index=0)},
            blocking=True,
        )

    # Verify that ServiceValidationError is raised when trying to turn off the light
    with pytest.raises(
        ServiceValidationError, match="Cannot operate light with active alerts"
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: get_entity_id(hass, entity_config, index=0)},
            blocking=True,
        )


@pytest.mark.parametrize(
    "entity_config", ["simple_light", "rgb", "warm_light"], indirect=True
)
async def test_light_turn_on(hass: HomeAssistant, setup_entity, entity_config) -> None:
    """Test turning on a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_off_value"]
    )

    assert light is not None
    assert light.state == STATE_OFF

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: get_entity_id(hass, entity_config)},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].brightness == 100


@pytest.mark.parametrize(
    "entity_config", ["simple_light", "rgb", "warm_light"], indirect=True
)
async def test_light_turn_off(hass: HomeAssistant, setup_entity, entity_config) -> None:
    """Test turning on a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_on_value"]
    )

    assert light is not None
    assert light.state == STATE_ON
    assert round(light.attributes["brightness"], 0) == 255.0

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: get_entity_id(hass, entity_config)},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].brightness == 0


@pytest.mark.parametrize(
    "entity_config", ["simple_light", "rgb", "warm_light"], indirect=True
)
async def test_light_brightness(
    hass: HomeAssistant, setup_entity, entity_config
) -> None:
    """Test setting brightness of a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_off_value"]
    )

    assert light is not None
    assert light.state == STATE_OFF
    assert not light.attributes["brightness"]

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: get_entity_id(hass, entity_config), ATTR_BRIGHTNESS: 128},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].brightness == 50


@pytest.mark.parametrize(
    "entity_config",
    [
        "rgb",
    ],
    indirect=True,
)
async def test_light_rgb(hass: HomeAssistant, setup_entity, entity_config) -> None:
    """Test setting RGB color of a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_on_value"]
    )

    assert light is not None
    assert light.state == STATE_ON
    assert "rgb_color" in light.attributes

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: get_entity_id(hass, entity_config),
                ATTR_RGB_COLOR: (32, 64, 128),
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        rgb_value = getattr(ha_value, entity_config["device_type"])[0]
        assert rgb_value.r == 32
        assert rgb_value.g == 64
        assert rgb_value.b == 128


@pytest.mark.parametrize(
    "entity_config",
    [
        "rgbw",
    ],
    indirect=True,
)
async def test_light_rgbw(hass: HomeAssistant, setup_entity, entity_config) -> None:
    """Test setting RGBW color of a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_on_value"], index=0
    )

    assert light is not None
    assert light.state == STATE_ON
    assert "rgbw_color" in light.attributes

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: get_entity_id(hass, entity_config, 0),
                ATTR_RGBW_COLOR: (128, 128, 128, 255),
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        rgbw_value = getattr(ha_value, entity_config["device_type"])[0]
        assert rgbw_value.r == 50
        assert rgbw_value.g == 50
        assert rgbw_value.b == 50
        assert rgbw_value.w == 100


@pytest.mark.parametrize(
    "entity_config",
    [
        "warm_light",
    ],
    indirect=True,
)
async def test_light_color_temp_min(
    hass: HomeAssistant, setup_entity, entity_config
) -> None:
    """Test setting color temperature of a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_on_value"]
    )

    assert light is not None
    assert light.state == STATE_ON
    assert light.attributes["color_temp_kelvin"] == 6500

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: get_entity_id(hass, entity_config),
                ATTR_COLOR_TEMP_KELVIN: 2700,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].relative_ct == 0


@pytest.mark.parametrize(
    "entity_config",
    [
        "warm_light",
    ],
    indirect=True,
)
async def test_light_color_temp_max(
    hass: HomeAssistant, setup_entity, entity_config
) -> None:
    """Test setting color temperature of a light."""
    light = await setup_entity(
        entity_config, status_value=entity_config["light_off_value"]
    )

    assert light is not None
    assert light.state == STATE_OFF
    assert not light.attributes["color_temp_kelvin"]

    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: get_entity_id(hass, entity_config),
                ATTR_COLOR_TEMP_KELVIN: 6500,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

        ha_value = mock_set_state.call_args.args[0]
        assert getattr(ha_value, entity_config["device_type"])[0].relative_ct == 100
