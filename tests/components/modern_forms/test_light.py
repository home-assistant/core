"""Tests for the Modern Forms light platform."""

from typing import Any
from unittest.mock import patch

from aiomodernforms import ModernFormsConnectionError
import pytest
from yarl import URL

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.components.modern_forms.const import (
    ATTR_SLEEP_TIME,
    DOMAIN,
    SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
    SERVICE_SET_LIGHT_SLEEP_TIMER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration, init_integration_gen4, modern_forms_gen4_call_mock

from tests.common import async_load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


async def test_light_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation and values of the Modern Forms lights."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("light.modernformsfan_light")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan Light"
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.modernformsfan_light")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF"


async def test_change_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the change of state of the Modern Forms segments."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            on=False,
        )

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.modernformsfan_light", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(on=True, brightness=100)


async def test_sleep_timer_services(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the change of state of the Modern Forms segments."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "light.modernformsfan_light", ATTR_SLEEP_TIME: 1},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(sleep=60)

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(sleep=0)


async def test_light_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test error handling of the Modern Forms lights."""

    await init_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()

    aioclient_mock.post("http://192.168.1.123:80/mf", text="", status=400)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_response"


async def test_light_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the Modern Forms lights."""
    await init_integration(hass, aioclient_mock)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.light",
            side_effect=ModernFormsConnectionError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"

    state = hass.states.get("light.modernformsfan_light")
    assert state.state == STATE_UNAVAILABLE


async def test_light_state_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a multi-fixture Gen4 fan creates one light entity per fixture."""
    await init_integration_gen4(hass, aioclient_mock)

    state = hass.states.get("light.modernformsfan_uplight")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan Uplight"
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 204

    entry = entity_registry.async_get("light.modernformsfan_uplight")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_2"

    state = hass.states.get("light.modernformsfan_downlight")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan Downlight"
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_BRIGHTNESS) is None

    entry = entity_registry.async_get("light.modernformsfan_downlight")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_3"


async def test_light_name_requires_word_boundary_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a fixture name isn't stripped without a real device-name boundary."""

    async def partial_word_name_mock(
        hass: HomeAssistant, method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Serve the normal Gen4 fixtures, with the uplight renamed."""
        if not url.path.endswith("/fixture"):
            return await modern_forms_gen4_call_mock(hass, method, url, data)
        payload = await async_load_json_object_fixture(
            hass, "fixture_gen4.json", DOMAIN
        )
        for fixture in payload["fixture"]:
            if fixture["addr"] == 2:
                fixture["name"] = "ModernFormsFancy Light"
        return AiohttpClientMockResponse(method=method, url=url, json=payload)

    await init_integration_gen4(hass, aioclient_mock, mock_type=partial_word_name_mock)

    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, DOMAIN, "AA:BB:CC:00:11:22_2"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "ModernFormsFan ModernFormsFancy Light"
    )


async def test_light_name_falls_back_to_device_name_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a fixture named exactly like the device falls back to that name alone."""

    async def exact_match_name_mock(
        hass: HomeAssistant, method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Serve the normal Gen4 fixtures, with the uplight renamed."""
        if not url.path.endswith("/fixture"):
            return await modern_forms_gen4_call_mock(hass, method, url, data)
        payload = await async_load_json_object_fixture(
            hass, "fixture_gen4.json", DOMAIN
        )
        for fixture in payload["fixture"]:
            if fixture["addr"] == 2:
                fixture["name"] = "ModernFormsFan"
        return AiohttpClientMockResponse(method=method, url=url, json=payload)

    await init_integration_gen4(hass, aioclient_mock, mock_type=exact_match_name_mock)

    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, DOMAIN, "AA:BB:CC:00:11:22_2"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan"


async def test_light_unavailable_when_fixture_disappears_gen4(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a Gen4 light entity goes unavailable if its fixture disappears."""
    removed_addresses: set[int] = set()

    async def fixture_removal_mock(
        hass: HomeAssistant, method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Serve the normal Gen4 fixtures, minus any addresses removed."""
        if not url.path.endswith("/fixture") or not removed_addresses:
            return await modern_forms_gen4_call_mock(hass, method, url, data)
        payload = await async_load_json_object_fixture(
            hass, "fixture_gen4.json", DOMAIN
        )
        payload["fixture"] = [
            fixture
            for fixture in payload["fixture"]
            if fixture["addr"] not in removed_addresses
        ]
        return AiohttpClientMockResponse(method=method, url=url, json=payload)

    entry = await init_integration_gen4(
        hass, aioclient_mock, mock_type=fixture_removal_mock
    )

    state = hass.states.get("light.modernformsfan_uplight")
    assert state
    assert state.state == STATE_ON

    removed_addresses.add(2)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("light.modernformsfan_uplight")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_light_change_state_gen4(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Gen4 fixture entities control via light_fixture(), not light()."""
    await init_integration_gen4(hass, aioclient_mock)

    with (
        patch("aiomodernforms.ModernFormsDevice.light_fixture") as light_fixture_mock,
        patch("aiomodernforms.ModernFormsDevice.light") as light_mock,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_uplight"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_fixture_mock.assert_called_once_with(2, on=False)
        light_mock.assert_not_called()


async def test_light_sleep_timer_not_supported_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting a sleep timer on a Gen4 light fixture raises an error."""
    await init_integration_gen4(hass, aioclient_mock)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "light.modernformsfan_uplight", ATTR_SLEEP_TIME: 1},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "sleep_timer_not_supported"


async def test_clear_light_sleep_timer_not_supported_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test clearing a sleep timer on a Gen4 light fixture raises an error."""
    await init_integration_gen4(hass, aioclient_mock)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "light.modernformsfan_uplight"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "sleep_timer_not_supported"


async def test_light_color_temp_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Gen4 light fixtures advertise and control color temperature."""
    await init_integration_gen4(hass, aioclient_mock)

    state = hass.states.get("light.modernformsfan_uplight")
    assert state
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) == 3000
    assert state.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN) == 2700
    assert state.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN) == 5000
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.COLOR_TEMP]

    with patch("aiomodernforms.ModernFormsDevice.light_fixture") as light_fixture_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.modernformsfan_uplight",
                ATTR_COLOR_TEMP_KELVIN: 4000,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        light_fixture_mock.assert_called_once_with(2, on=True, color_temp_kelvin=4000)


async def test_light_color_temp_missing_bounds_gen4(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a Gen4 fixture missing color-temp bounds falls back to brightness."""

    async def missing_bounds_mock(
        hass: HomeAssistant, method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Serve the normal Gen4 fixtures, minus the downlight's color-temp bounds."""
        if not url.path.endswith("/fixture"):
            return await modern_forms_gen4_call_mock(hass, method, url, data)
        payload = await async_load_json_object_fixture(
            hass, "fixture_gen4.json", DOMAIN
        )
        for fixture in payload["fixture"]:
            if fixture["addr"] == 3:
                fixture["detail"] = {}
        return AiohttpClientMockResponse(method=method, url=url, json=payload)

    await init_integration_gen4(hass, aioclient_mock, mock_type=missing_bounds_mock)

    state = hass.states.get("light.modernformsfan_downlight")
    assert state
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.BRIGHTNESS]
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) is None


async def test_light_no_color_temp_on_legacy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Gen 1/2/3 lights never advertise color temperature."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("light.modernformsfan_light")
    assert state
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.BRIGHTNESS]
