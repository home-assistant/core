"""Tests for itachip2ir infrared entities."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

from pyitach import ItachBusyError, ItachCommandError, ItachConnectionError
import pytest

from homeassistant.components.infrared import InfraredCommand
from homeassistant.components.itachip2ir.infrared import ItachInfraredEntity
from homeassistant.exceptions import HomeAssistantError

HOST = "192.168.1.211"
DEVICE_ID = "GlobalCache_000C1E123456"


class FakeClient:
    """Fake iTach client."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        """Initialize fake client."""
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def async_send_ir(
        self,
        module: int,
        connector: int,
        carrier_frequency: int,
        timings: list[int],
    ) -> None:
        """Record sent IR command or raise configured error."""
        if self.error is not None:
            raise self.error

        self.calls.append(
            {
                "module": module,
                "connector": connector,
                "carrier_frequency": carrier_frequency,
                "timings": timings,
            }
        )


class FakeCommand:
    """Fake Home Assistant InfraredCommand."""

    def __init__(
        self,
        *,
        modulation: int | str = 38_000,
        timings: list[Any] | None = None,
    ) -> None:
        """Initialize fake command."""
        self.modulation = modulation
        self._timings = timings or [
            SimpleNamespace(high_us=9000, low_us=4500),
            SimpleNamespace(high_us=562, low_us=40_000),
        ]

    def get_raw_timings(self) -> list[Any]:
        """Return fake raw timings."""
        return self._timings


def _entity(
    *,
    client: FakeClient | None = None,
    mode: str = "IR",
    port: int = 1,
) -> ItachInfraredEntity:
    """Create an iTach infrared entity."""
    entity = ItachInfraredEntity(
        host=HOST,
        device_id=DEVICE_ID,
        ir_module=1,
        ir_port=port,
        mode=mode,
        client=client or FakeClient(),  # type: ignore[arg-type]
    )
    entity.hass = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_infrared_converts_timings() -> None:
    """Test raw timings are converted to Global Caché cycles."""
    client = FakeClient()
    entity = _entity(client=client)

    await entity.async_send_command(cast(InfraredCommand, FakeCommand()))

    assert client.calls == [
        {
            "module": 1,
            "connector": 1,
            "carrier_frequency": 38_000,
            "timings": [342, 171, 21, 1520],
        }
    ]


@pytest.mark.asyncio
async def test_infrared_rejects_non_positive_timings() -> None:
    """Test zero and negative timings are rejected as invalid commands."""
    client = FakeClient()
    entity = _entity(client=client)

    command = FakeCommand(
        timings=[
            SimpleNamespace(high_us=1000, low_us=1000),
            SimpleNamespace(high_us=0, low_us=-5),
        ]
    )

    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_send_command(cast(InfraredCommand, command))

    assert exc.value.translation_domain == "itachip2ir"
    assert exc.value.translation_key == "itach_invalid_command"
    assert exc.value.translation_placeholders is not None
    assert "timing durations" in exc.value.translation_placeholders["error"]
    assert client.calls == []


def test_ir_port_entity_translation_and_unique_id() -> None:
    """Test normal IR port uses translated naming metadata."""
    entity = _entity(mode="IR", port=1)

    assert entity.translation_key == "ir_port"
    assert entity.translation_placeholders == {"port": "1"}
    assert entity.unique_id == f"{DEVICE_ID}_port_1"


def test_ir_blaster_entity_translation_and_unique_id() -> None:
    """Test IR blaster port uses translated naming metadata."""
    entity = _entity(mode="IR_BLASTER", port=3)

    assert entity.translation_key == "ir_blaster_port"
    assert entity.translation_placeholders == {"port": "3"}
    assert entity.unique_id == f"{DEVICE_ID}_port_3"


def test_device_info() -> None:
    """Test device registry information."""
    entity = _entity()

    assert entity.device_info["identifiers"] == {("itachip2ir", DEVICE_ID)}
    assert entity.device_info["name"] == f"iTach IP2IR ({HOST})"
    assert entity.device_info["manufacturer"] == "Global Caché"
    assert entity.device_info["model"] == "iTach IP2IR"
    assert entity.device_info["configuration_url"] == f"http://{HOST}"


@pytest.mark.asyncio
async def test_send_command_busy_error_raises_translated_error() -> None:
    """Test busy iTach error is translated."""
    entity = _entity(client=FakeClient(error=ItachBusyError("busy")))

    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_send_command(cast(InfraredCommand, FakeCommand()))

    assert exc.value.translation_domain == "itachip2ir"
    assert exc.value.translation_key == "itach_busy"


@pytest.mark.asyncio
async def test_send_command_rejected_error_raises_translated_error() -> None:
    """Test rejected command error is translated."""
    entity = _entity(client=FakeClient(error=ItachCommandError("bad command")))

    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_send_command(cast(InfraredCommand, FakeCommand()))

    assert exc.value.translation_domain == "itachip2ir"
    assert exc.value.translation_key == "itach_rejected_command"
    assert exc.value.translation_placeholders == {"error": "bad command"}


@pytest.mark.asyncio
async def test_send_command_connection_error_marks_unavailable_once() -> None:
    """Test connection failure marks entity unavailable and writes state once."""
    entity = _entity(client=FakeClient(error=ItachConnectionError("offline")))

    assert entity.available

    with patch.object(entity, "async_write_ha_state") as write_state:
        with pytest.raises(HomeAssistantError) as exc:
            await entity.async_send_command(cast(InfraredCommand, FakeCommand()))

        assert exc.value.translation_domain == "itachip2ir"
        assert exc.value.translation_key == "itach_connection_failed"
        assert exc.value.translation_placeholders == {"error": "offline"}
        assert not entity.available
        write_state.assert_called_once()

        with pytest.raises(HomeAssistantError):
            await entity.async_send_command(cast(InfraredCommand, FakeCommand()))

        write_state.assert_called_once()


@pytest.mark.asyncio
async def test_send_command_success_after_unavailable_marks_available() -> None:
    """Test successful send after failure marks entity available again."""
    client = FakeClient()
    entity = _entity(client=client)
    entity._attr_available = False

    with patch.object(entity, "async_write_ha_state") as write_state:
        await entity.async_send_command(cast(InfraredCommand, FakeCommand()))

    assert entity.available
    write_state.assert_called_once()
    assert client.calls


def test_command_to_gc_timings_rejects_empty_raw_timings() -> None:
    """Test raw timing conversion rejects commands without raw timings."""
    entity = _entity()
    command = MagicMock()
    command.get_raw_timings.return_value = []

    with pytest.raises(
        ValueError,
        match="IR command contains no usable raw timings",
    ):
        entity._command_to_gc_timings(command, 38_000)


def test_device_connections_invalid_device_id_returns_empty() -> None:
    """Test invalid device IDs produce no network MAC connections."""
    entity = _entity()
    entity._device_id = "invalid"

    assert entity.device_info["connections"] == set()


@pytest.mark.asyncio
async def test_infrared_rejects_non_positive_carrier_frequency() -> None:
    """Test invalid carrier frequency is rejected."""
    client = FakeClient()
    entity = _entity(client=client)

    command = FakeCommand(modulation=0)

    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_send_command(cast(InfraredCommand, command))

    assert exc.value.translation_domain == "itachip2ir"
    assert exc.value.translation_key == "itach_invalid_command"
    assert exc.value.translation_placeholders == {
        "error": "Carrier frequency must be greater than zero"
    }
    assert client.calls == []
