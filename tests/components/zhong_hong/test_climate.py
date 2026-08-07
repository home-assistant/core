"""Test the zhong_hong climate platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

ENTITY_ID = "climate.zhong_hong_hvac_1_1"
HOST = "1.2.3.4"


class FakeGateway:
    """Test double for the zhong_hong_hvac gateway."""

    def __init__(self) -> None:
        """Initialize the fake gateway."""
        self.connected = True
        self.send_result = True
        self.query_status_calls = 0

    @property
    def gw_addr(self) -> int:
        """Return the gateway address."""
        return 1

    def add_status_callback(self, ac_addr, callback) -> None:
        """Register a status callback (no-op)."""

    def add_device(self, device) -> None:
        """Register a device (no-op)."""

    def discovery_ac(self) -> list[tuple[int, int]]:
        """Return the discovered device addresses."""
        return [(1, 1)]

    def start_listen(self) -> None:
        """Start listening (no-op)."""

    def query_all_status(self) -> None:
        """Query all devices (no-op)."""

    def stop_listen(self) -> None:
        """Stop listening (no-op)."""

    def query_status(self, ac_addr) -> bool:
        """Query the status of a device."""
        self.query_status_calls += 1
        return self.send_result

    def send(self, ac_data) -> bool:
        """Send a command to the gateway."""
        return self.send_result


@pytest.fixture
def gateway() -> FakeGateway:
    """Return a fake gateway."""
    return FakeGateway()


async def _setup_climate(hass: HomeAssistant, gateway: FakeGateway) -> None:
    """Set up the zhong_hong climate platform with a fake gateway."""
    with patch(
        "homeassistant.components.zhong_hong.climate.ZhongHongGateway",
        return_value=gateway,
    ):
        assert await async_setup_component(
            hass,
            CLIMATE_DOMAIN,
            {CLIMATE_DOMAIN: {"platform": "zhong_hong", "host": HOST}},
        )
        # Platform setup runs in a fire-and-forget task, so the patch must
        # stay active until it completes.
        await hass.async_block_till_done()


async def test_setup_creates_entity(hass: HomeAssistant, gateway: FakeGateway) -> None:
    """Test the entity is created and polling is enabled."""
    await _setup_climate(hass, gateway)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    assert entity.should_poll is True


async def test_unavailable_when_gateway_disconnected(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test the entity is unavailable when the gateway connection is unhealthy."""
    gateway.connected = False
    await _setup_climate(hass, gateway)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_update_queries_gateway_when_connected(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test update polls the gateway when the connection is healthy."""
    await _setup_climate(hass, gateway)

    entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    await entity.async_device_update()

    assert gateway.query_status_calls == 1


async def test_update_skips_gateway_when_disconnected(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test update does not poll the gateway when the connection is unhealthy."""
    gateway.connected = False
    await _setup_climate(hass, gateway)

    entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    await entity.async_device_update()

    assert gateway.query_status_calls == 0


async def test_turn_on_success(hass: HomeAssistant, gateway: FakeGateway) -> None:
    """Test turn_on does not raise when the command is sent."""
    await _setup_climate(hass, gateway)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )


async def test_turn_on_send_failure_raises(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test turn_on raises when the command cannot be sent."""
    gateway.send_result = False
    await _setup_climate(hass, gateway)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": "turn-on"}


async def test_turn_off_send_failure_raises(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test turn_off raises when the command cannot be sent."""
    gateway.send_result = False
    await _setup_climate(hass, gateway)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": "turn-off"}


async def test_set_temperature_send_failure_raises(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test set_temperature raises when the command cannot be sent."""
    gateway.send_result = False
    await _setup_climate(hass, gateway)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25},
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": "temperature"}


async def test_set_hvac_mode_send_failure_raises(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test set_hvac_mode raises when the command cannot be sent."""
    gateway.send_result = False
    await _setup_climate(hass, gateway)

    # The device must already be on, otherwise turn_on() fails first
    # and the mode command is never attempted.
    entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    entity._device.switch_status = "ON"

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": "mode"}


async def test_set_hvac_mode_success(hass: HomeAssistant, gateway: FakeGateway) -> None:
    """Test set_hvac_mode does not raise when the command is sent."""
    await _setup_climate(hass, gateway)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )


async def test_set_fan_mode_unsupported_logs_error(
    hass: HomeAssistant, gateway: FakeGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """Test set_fan_mode with an unsupported mode logs an error and sends nothing."""
    await _setup_climate(hass, gateway)

    entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    await entity.async_set_fan_mode("unknown")

    assert "Unsupported fan mode: unknown" in caplog.text
    assert "failed to send" not in caplog.text


async def test_set_fan_mode_send_failure_raises(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """Test set_fan_mode raises when the command cannot be sent."""
    gateway.send_result = False
    await _setup_climate(hass, gateway)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: FAN_LOW},
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": "fan"}


async def test_set_fan_mode_success(hass: HomeAssistant, gateway: FakeGateway) -> None:
    """Test set_fan_mode does not raise when the command is sent."""
    await _setup_climate(hass, gateway)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )
