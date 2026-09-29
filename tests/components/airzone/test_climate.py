"""The climate tests for the Airzone platform."""

from collections.abc import Generator
import copy
from unittest.mock import patch

from aioairzone.const import (
    API_COOL_SET_POINT,
    API_DATA,
    API_HEAT_SET_POINT,
    API_MAX_TEMP,
    API_MIN_TEMP,
    API_ON,
    API_SET_POINT,
    API_SPEED,
    API_SYSTEM_ID,
    API_SYSTEMS,
    API_ZONE_ID,
)
from aioairzone.exceptions import AirzoneError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airzone.coordinator import SCAN_INTERVAL
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityCapabilityAttribute,
    ClimateEntityStateAttribute,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .util import (
    HVAC_DHW_MOCK,
    HVAC_MOCK,
    HVAC_SYSTEMS_MOCK,
    HVAC_WEBSERVER_MOCK,
    async_init_integration,
)

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.airzone.PLATFORMS", [Platform.CLIMATE]):
        yield


async def test_airzone_create_climates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of climates."""

    config_entry = await async_init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_airzone_climate_update_temp_limits(hass: HomeAssistant) -> None:
    """Test climate temperature limits are refreshed from the API."""

    await async_init_integration(hass)

    HVAC_MOCK_CHANGED = copy.deepcopy(HVAC_MOCK)
    HVAC_MOCK_CHANGED[API_SYSTEMS][0][API_DATA][0][API_MAX_TEMP] = 25
    HVAC_MOCK_CHANGED[API_SYSTEMS][0][API_DATA][0][API_MIN_TEMP] = 10

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
            return_value=HVAC_DHW_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
            return_value=HVAC_MOCK_CHANGED,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
            return_value=HVAC_SYSTEMS_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
            return_value=HVAC_WEBSERVER_MOCK,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("climate.salon")
    assert state.attributes.get(ClimateEntityCapabilityAttribute.MAX_TEMP) == 25
    assert state.attributes.get(ClimateEntityCapabilityAttribute.MIN_TEMP) == 10


async def test_airzone_climate_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning on."""

    await async_init_integration(hass)

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_ON: 1,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "climate.salon",
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.HEAT

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_ON: 0,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "climate.salon",
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.OFF

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 2,
                API_ZONE_ID: 1,
                API_ON: 1,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "climate.airzone_2_1",
            },
            blocking=True,
        )

    state = hass.states.get("climate.airzone_2_1")
    assert state.state == HVACMode.HEAT_COOL


async def test_airzone_climate_set_hvac_mode(hass: HomeAssistant) -> None:
    """Test setting the HVAC mode."""

    await async_init_integration(hass)

    HVAC_MOCK_1 = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_ON: 1,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_1,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.COOL

    HVAC_MOCK_2 = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_ON: 0,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_2,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.OFF

    HVAC_MOCK_3 = {
        API_DATA: [
            {
                API_SYSTEM_ID: 2,
                API_ZONE_ID: 1,
                API_ON: 1,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_3,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.airzone_2_1",
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            blocking=True,
        )

    state = hass.states.get("climate.airzone_2_1")
    assert state.state == HVACMode.HEAT_COOL

    HVAC_MOCK_4 = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_ON: 1,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_4,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVACMode.FAN_ONLY,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.FAN_ONLY

    HVAC_MOCK_NO_SET_POINT = copy.deepcopy(HVAC_MOCK)
    del HVAC_MOCK_NO_SET_POINT[API_SYSTEMS][0][API_DATA][0][API_SET_POINT]

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
            return_value=HVAC_DHW_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
            return_value=HVAC_MOCK_NO_SET_POINT,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
            return_value=HVAC_SYSTEMS_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
            return_value=HVAC_WEBSERVER_MOCK,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    state = hass.states.get("climate.salon")
    assert state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 19.1


async def test_airzone_climate_set_hvac_slave_error(hass: HomeAssistant) -> None:
    """Test setting the HVAC mode for a slave zone."""

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 5,
                API_ON: 1,
            }
        ]
    }

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
            return_value=HVAC_MOCK,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.dorm_2",
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dorm_2")
    assert state.state == HVACMode.HEAT


async def test_airzone_climate_set_fan_mode(hass: HomeAssistant) -> None:
    """Test setting the target temperature."""

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_SPEED: 2,
            }
        ]
    }

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_FAN_MODE: FAN_MEDIUM,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.attributes.get(ClimateEntityStateAttribute.FAN_MODE) == FAN_MEDIUM


async def test_airzone_climate_set_temp(hass: HomeAssistant) -> None:
    """Test setting the target temperature."""

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 5,
                API_SET_POINT: 20.5,
                API_ON: 1,
            }
        ]
    }

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.dorm_2",
                ATTR_HVAC_MODE: HVACMode.HEAT,
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dorm_2")
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 20.5


async def test_airzone_climate_set_temp_error(hass: HomeAssistant) -> None:
    """Test error when setting the target temperature."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
            side_effect=AirzoneError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.dorm_2",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dorm_2")
    assert state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 19.5


async def test_airzone_climate_set_temp_range(hass: HomeAssistant) -> None:
    """Test setting the target temperature range."""

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 3,
                API_ZONE_ID: 1,
                API_COOL_SET_POINT: 77.0,
                API_HEAT_SET_POINT: 68.0,
            }
        ]
    }

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.dkn_plus",
                ATTR_TARGET_TEMP_HIGH: 25.0,
                ATTR_TARGET_TEMP_LOW: 20.0,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dkn_plus")
    assert state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMP_HIGH) == 25.0
    assert state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMP_LOW) == 20.0
