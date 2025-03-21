"""Test the Axion DMX light."""

import asyncio
from unittest.mock import patch

from homeassistant.components.axion_dmx.const import (
    CONF_CHANNEL,
    CONF_HOST,
    CONF_LIGHT_TYPE,
    CONF_PASSWORD,
    DOMAIN,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_ID = "light.axion_light_1"


async def test_name(hass: HomeAssistant) -> None:
    """Test the name property."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgb",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        entity_registry = hass.states.get(ENTITY_ID)
        assert entity_registry is not None
        assert entity_registry.name == "Axion Light 1"


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test the unique_id property."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgb",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.get_name",
            return_value="DMX-0D2370",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify entity registry
        entity_registry = er.async_get(hass)
        light = entity_registry.async_get(ENTITY_ID)
        assert light is not None
        assert light.unique_id == "axion_dmx_light_DMX-0D2370_1"


async def test_is_off(hass: HomeAssistant) -> None:
    """Test the is_on property."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgb",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        entity_registry = hass.states.get(ENTITY_ID)
        assert entity_registry.state == STATE_OFF


async def test_brightness(hass: HomeAssistant) -> None:
    """Test the brightness property."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgb",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
    ):
        # Set up the component
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Simulate turning on the light with brightness
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_BRIGHTNESS: 128,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        # Wait for coordinator to update the state
        await asyncio.sleep(1)

        # Verify the state of the entity
        entity_state = hass.states.get(ENTITY_ID)
        assert entity_state is not None
        assert entity_state.state == STATE_ON

        # Check that the brightness attribute is correctly updated
        assert entity_state.attributes.get(ATTR_BRIGHTNESS) == 128


async def test_color_mode(hass: HomeAssistant) -> None:
    """Test the color_mode property."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgbw",
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        entity_registry = hass.states.get(ENTITY_ID)
        assert entity_registry.attributes.get("supported_color_modes") == [
            "brightness",
            "rgbw",
        ]


async def test_hs_color(hass: HomeAssistant) -> None:
    """Test setting and getting the HS color."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgb",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.set_color"
        ) as mock_set_color,
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
        patch(
            "homeassistant.util.color.color_hs_to_RGB",
            return_value=(255, 128, 0),
        ) as mock_color_hs_to_RGB,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify entity registry
        entity_registry = er.async_get(hass)
        light = entity_registry.async_get(ENTITY_ID)
        assert light is not None

        # Simulate turning on the light with HS color
        hs_color = (30, 100)
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_HS_COLOR: hs_color,
                ATTR_BRIGHTNESS: 255,
            },
            blocking=True,
        )

        # Wait for coordinator to update the state
        await asyncio.sleep(1)

        # Verify the state of the entity
        entity_state = hass.states.get(ENTITY_ID)
        assert entity_state is not None
        assert entity_state.state == STATE_ON

        # Assert the API call with the converted RGB value
        mock_color_hs_to_RGB.assert_called_with(*hs_color)
        mock_set_color.assert_called_once_with(0, [255, 128, 0])


async def test_color_temp(hass: HomeAssistant) -> None:
    """Test the color temperature setting."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "tunable_white",
        },
    )
    entry.add_to_hass(hass)

    color_temp_kelvin = 4000  # Color temperature in Kelvin
    expected_mired = 250  # Expected mired value after conversion

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
        patch(
            "homeassistant.components.axion_dmx.light.color_util.color_temperature_kelvin_to_mired",
            return_value=expected_mired,
        ) as mock_kelvin_to_mired,
    ):
        # Setup the component and ensure it initializes correctly
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify entity is added
        entity_state = hass.states.get(ENTITY_ID)
        assert entity_state is not None

        # Call the turn_on service with color temperature
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_COLOR_TEMP: expected_mired,
            },
            blocking=True,
        )

        # Wait for coordinator to update the state
        await asyncio.sleep(1)

        # Verify the state of the entity
        entity_state = hass.states.get(ENTITY_ID)
        assert entity_state is not None
        assert entity_state.state == STATE_ON

        # Validate the mock conversion
        mock_kelvin_to_mired.assert_called_with(color_temp_kelvin)


async def test_rgbw_light(hass: HomeAssistant) -> None:
    """Test controlling an RGBW light."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgbw",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.set_rgbw"
        ) as mock_set_rgbw,
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),  # Mock the network interaction
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        light = entity_registry.async_get(ENTITY_ID)
        assert light is not None

        # Simulate turning on the light
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_RGBW_COLOR: [255, 0, 0, 0],
                ATTR_BRIGHTNESS: 128,
            },
            blocking=True,
        )

        # Wait for coordinator to update the state
        await asyncio.sleep(1)

        # Verify the state of the entity
        entity_state = hass.states.get(ENTITY_ID)
        assert entity_state is not None
        assert entity_state.state == STATE_ON

        # Verify set_rgbw was called correctly
        mock_set_rgbw.assert_called_with(0, [128, 0, 0, 0])


async def test_rgbww_light(hass: HomeAssistant) -> None:
    """Test controlling an RGBWW light."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_CHANNEL: 1,
            CONF_LIGHT_TYPE: "rgbww",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.set_rgbww"
        ) as mock_set_rgbww,
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),  # Mock the network interaction
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        light = entity_registry.async_get(ENTITY_ID)
        assert light is not None

        # Simulate turning on the light
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_RGBWW_COLOR: [255, 255, 0, 0, 0],
                ATTR_BRIGHTNESS: 255,
            },
            blocking=True,
        )

        # Wait for coordinator to update the state
        await asyncio.sleep(1)

        # Verify the state of the entity
        entity_state = hass.states.get(ENTITY_ID)
        assert entity_state is not None
        assert entity_state.state == STATE_ON

        # Verify set_rgbw was called correctly
        mock_set_rgbww.assert_called_with(0, [255, 255, 0, 0, 0])
