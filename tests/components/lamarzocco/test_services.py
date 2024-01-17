"""Test the LaMarzocco services."""
from unittest.mock import MagicMock

from lmcloud.exceptions import RequestNotSuccessful
import pytest

from homeassistant.components.lamarzocco.const import (
    CONF_CONFIG_ENTRY,
    CONF_DAY_OF_WEEK,
    CONF_ENABLE,
    CONF_HOUR_OFF,
    CONF_HOUR_ON,
    CONF_MINUTE_OFF,
    CONF_MINUTE_ON,
    DOMAIN,
    SERVICE_AUTO_ON_OFF_ENABLE,
    SERVICE_AUTO_ON_OFF_TIMES,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_service_auto_on_off_enable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco auto on/off enable service."""

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_ENABLE,
        {
            CONF_CONFIG_ENTRY: mock_config_entry.entry_id,
            CONF_DAY_OF_WEEK: "mon",
            CONF_ENABLE: True,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_enable.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_enable.assert_called_once_with(
        day_of_week="mon", enable=True
    )


async def test_service_call_error(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an exception during the service call."""
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
                CONF_CONFIG_ENTRY: mock_config_entry.entry_id,
                CONF_DAY_OF_WEEK: "mon",
                CONF_ENABLE: True,
            },
            blocking=True,
        )


async def test_invalid_config_entry(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test validation error for invalid config entry."""
    entry_id = "invalid"
    with pytest.raises(
        ServiceValidationError,
        match=f"Invalid config entry: {entry_id}",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AUTO_ON_OFF_ENABLE,
            {
                CONF_CONFIG_ENTRY: entry_id,
                CONF_DAY_OF_WEEK: "mon",
                CONF_ENABLE: True,
            },
            blocking=True,
        )


async def test_unloaded_config_entry(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test validation error for unloaded config entry."""

    await mock_config_entry.async_unload(hass)

    with pytest.raises(
        ServiceValidationError,
        match=f"Config entry {mock_config_entry.title} is not loaded",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AUTO_ON_OFF_ENABLE,
            {
                CONF_CONFIG_ENTRY: mock_config_entry.entry_id,
                CONF_DAY_OF_WEEK: "mon",
                CONF_ENABLE: True,
            },
            blocking=True,
        )


async def test_service_set_auto_on_off_times(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco auto on/off times service."""

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_TIMES,
        {
            CONF_CONFIG_ENTRY: mock_config_entry.entry_id,
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
