"""Test the LaMarzocco services."""
from unittest.mock import MagicMock

from lmcloud.exceptions import RequestNotSuccessful
import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.lamarzocco.services import (
    CONF_DAY_OF_WEEK,
    CONF_ENABLE,
    CONF_HOUR_OFF,
    CONF_HOUR_ON,
    CONF_KEY,
    CONF_MINUTE_OFF,
    CONF_MINUTE_ON,
    CONF_PULSES,
    CONF_SECONDS,
    CONF_SECONDS_OFF,
    CONF_SECONDS_ON,
    SERVICE_AUTO_ON_OFF_ENABLE,
    SERVICE_AUTO_ON_OFF_TIMES,
    SERVICE_DOSE,
    SERVICE_DOSE_HOT_WATER,
    SERVICE_PREBREW_TIMES,
    SERVICE_PREINFUSION_TIME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_service_auto_on_off_enable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco auto on/off enable service."""
    mock_lamarzocco.set_auto_on_off_enable.return_value = None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_ENABLE,
        {
            CONF_DAY_OF_WEEK: "mon",
            CONF_ENABLE: True,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_enable.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_enable.assert_called_once_with(
        day_of_week="mon", enable=True
    )

    mock_lamarzocco.set_auto_on_off_enable.side_effect = RequestNotSuccessful(
        "BadRequest"
    )
    with pytest.raises(
        HomeAssistantError, match="Service call encountered error: BadRequest"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AUTO_ON_OFF_ENABLE,
            {
                CONF_DAY_OF_WEEK: "mon",
                CONF_ENABLE: True,
            },
            blocking=True,
        )

    assert len(mock_lamarzocco.set_auto_on_off_enable.mock_calls) == 2


async def test_service_set_auto_on_off_times(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco auto on/off times service."""
    mock_lamarzocco.set_auto_on_off.return_value = None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_TIMES,
        {
            CONF_DAY_OF_WEEK: "tue",
            CONF_HOUR_ON: 8,
            CONF_MINUTE_ON: 30,
            CONF_HOUR_OFF: 17,
            CONF_MINUTE_OFF: 0,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off.assert_called_once_with(
        day_of_week="tue", hour_on=8, minute_on=30, hour_off=17, minute_off=0
    )


async def test_service_set_dose(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco set dose service."""
    mock_lamarzocco.set_dose.return_value = None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DOSE,
        {
            CONF_KEY: 2,
            CONF_PULSES: 300,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_dose.mock_calls) == 1
    mock_lamarzocco.set_dose.assert_called_once_with(key=2, value=300)


async def test_service_set_dose_hot_water(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco set dose hot water service."""
    mock_lamarzocco.set_dose_hot_water.return_value = None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DOSE_HOT_WATER,
        {
            CONF_SECONDS: 16,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_dose_hot_water.mock_calls) == 1
    mock_lamarzocco.set_dose_hot_water.assert_called_once_with(value=16)


async def test_service_set_prebrew_times(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco set prebrew times service."""
    mock_lamarzocco.set_prebrew_times.return_value = None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PREBREW_TIMES,
        {
            CONF_KEY: 3,
            CONF_SECONDS_ON: 4,
            CONF_SECONDS_OFF: 5,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew_times.mock_calls) == 1
    mock_lamarzocco.set_prebrew_times.assert_called_once_with(
        key=3, seconds_on=4, seconds_off=5
    )


async def test_service_set_preinfusion_time(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco set preinfusion time service."""
    mock_lamarzocco.set_prebrew_times.return_value = None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PREINFUSION_TIME,
        {
            CONF_KEY: 3,
            CONF_SECONDS: 6,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion_time.mock_calls) == 1
    mock_lamarzocco.set_preinfusion_time.assert_called_once_with(key=3, seconds=6)
