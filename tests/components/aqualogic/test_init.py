"""Tests for the AquaLogic integration setup."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.components.aqualogic import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_creates_processor(
    hass: HomeAssistant, mock_processor: MagicMock
) -> None:
    """Test setup registers the processor in hass.data."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
    )
    await hass.async_block_till_done()

    assert hass.data[DOMAIN] is mock_processor


async def test_processor_starts_on_ha_start(
    hass: HomeAssistant, mock_processor: MagicMock
) -> None:
    """Test the processor thread starts when Home Assistant starts."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_processor.start_listen.assert_called_once()


async def test_processor_shuts_down_on_ha_stop(
    hass: HomeAssistant, mock_processor: MagicMock
) -> None:
    """Test the processor shuts down when Home Assistant stops."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_processor.shutdown.assert_called_once()


async def test_processor_run_reconnects(hass: HomeAssistant) -> None:
    """Test the processor reconnects after a dropped connection."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
    )
    await hass.async_block_till_done()
    processor = hass.data[DOMAIN]

    connect_calls = 0

    def stop_on_second_connect(*args: object, **kwargs: object) -> None:
        nonlocal connect_calls
        connect_calls += 1
        if connect_calls >= 2:
            processor._shutdown = True

    # Patch RECONNECT_INTERVAL to zero so time.sleep(0) returns immediately
    with (
        patch("homeassistant.components.aqualogic.RECONNECT_INTERVAL", timedelta(0)),
        patch("homeassistant.components.aqualogic.AquaLogic") as mock_al,
    ):
        mock_al.return_value.connect.side_effect = stop_on_second_connect
        processor.run()

    assert connect_calls == 2
