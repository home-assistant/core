"""The select tests for the Airzone platform."""

from collections.abc import Generator
from unittest.mock import patch

from aioairzone.common import OperationMode, QAdapt
from aioairzone.const import (
    API_COLD_ANGLE,
    API_DATA,
    API_HEAT_ANGLE,
    API_MODE,
    API_Q_ADAPT,
    API_SLEEP,
    API_SYSTEM_ID,
    API_ZONE_ID,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .util import async_init_integration

from tests.common import snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.airzone.PLATFORMS", [Platform.SELECT]):
        yield


async def test_airzone_create_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of selects."""

    config_entry = await async_init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Mode selects are only created for master zones
    assert hass.states.get("select.despacho_mode") is None
    assert hass.states.get("select.dorm_1_mode") is None
    assert hass.states.get("select.dorm_2_mode") is None
    assert hass.states.get("select.dorm_ppal_mode") is None


async def test_airzone_select_sys_qadapt(hass: HomeAssistant) -> None:
    """Test select system Q-Adapt."""

    await async_init_integration(hass)

    put_q_adapt = {
        API_DATA: {
            API_SYSTEM_ID: 1,
            API_Q_ADAPT: QAdapt.SILENCE,
        }
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.system_1_q_adapt",
                ATTR_OPTION: "Invalid",
            },
            blocking=True,
        )

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_q_adapt,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.system_1_q_adapt",
                ATTR_OPTION: "silence",
            },
            blocking=True,
        )

    state = hass.states.get("select.system_1_q_adapt")
    assert state.state == "silence"

    put_q_adapt = {
        API_DATA: {
            API_SYSTEM_ID: 2,
            API_Q_ADAPT: QAdapt.SILENCE,
        }
    }

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
            return_value=put_q_adapt,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.system_1_q_adapt",
                ATTR_OPTION: "silence",
            },
            blocking=True,
        )


async def test_airzone_select_sleep(hass: HomeAssistant) -> None:
    """Test select sleep."""

    await async_init_integration(hass)

    put_hvac_sleep = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_SLEEP: 30,
            }
        ]
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_sleep",
                ATTR_OPTION: "Invalid",
            },
            blocking=True,
        )

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_sleep,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_sleep",
                ATTR_OPTION: "30m",
            },
            blocking=True,
        )

    state = hass.states.get("select.dorm_1_sleep")
    assert state.state == "30m"


async def test_airzone_select_mode(hass: HomeAssistant) -> None:
    """Test select HVAC mode."""

    await async_init_integration(hass)

    put_hvac_mode = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_MODE: OperationMode.COOLING,
            }
        ]
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.salon_mode",
                ATTR_OPTION: "Invalid",
            },
            blocking=True,
        )

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_mode,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.salon_mode",
                ATTR_OPTION: "cool",
            },
            blocking=True,
        )

    state = hass.states.get("select.salon_mode")
    assert state.state == "cool"


async def test_airzone_select_grille_angle(hass: HomeAssistant) -> None:
    """Test select sleep."""

    await async_init_integration(hass)

    # Cold Angle

    put_hvac_cold_angle = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_COLD_ANGLE: 1,
            }
        ]
    }

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_cold_angle,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_cold_angle",
                ATTR_OPTION: "50deg",
            },
            blocking=True,
        )

    state = hass.states.get("select.dorm_1_cold_angle")
    assert state.state == "50deg"

    # Heat Angle

    put_hvac_heat_angle = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_HEAT_ANGLE: 2,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_heat_angle,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_heat_angle",
                ATTR_OPTION: "45deg",
            },
            blocking=True,
        )

    state = hass.states.get("select.dorm_1_heat_angle")
    assert state.state == "45deg"
