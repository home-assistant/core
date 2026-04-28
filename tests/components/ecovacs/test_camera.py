"""Tests for the Ecovacs camera platform."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.components.ecovacs.config_flow import _device_pin_field_key
from homeassistant.components.ecovacs.const import CONF_CAMERA_PINS, DOMAIN
from deebot_client.camera.api import encode_pin
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Load only the camera platform."""
    return Platform.CAMERA


class TestCameraEntitySetup:
    """Tests for camera entity creation."""

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_camera_entity_created(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        snapshot: SnapshotAssertion,
    ) -> None:
        """Camera entity is created for each modern device."""
        entry = entity_registry.async_get("camera.ozmo_950_camera")
        assert entry is not None
        assert entry.domain == "camera"
        assert entry.unique_id.endswith("_camera")
        assert entry == snapshot(name="camera:entity-registry")

    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_camera_entity_disabled_by_default(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
    ) -> None:
        """Camera entity is disabled by default."""
        entries = er.async_entries_for_config_entry(
            entity_registry, hass.config_entries.async_entries(DOMAIN)[0].entry_id
        )
        camera_entries = [e for e in entries if e.domain == "camera"]
        assert all(e.disabled_by is not None for e in camera_entries)


class TestCameraOnOff:
    """Tests for ON/OFF feature."""

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_camera_off_by_default(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Camera returns black placeholder when no stream is started yet."""
        image = await async_get_image(hass, "camera.ozmo_950_camera")
        # Should return the black JPEG placeholder, not raise
        assert image.content.startswith(b"\xff\xd8")

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_turn_on_starts_session(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """Turning on camera starts a KVS session."""
        _, session_instance = mock_kvs_stream_session
        await hass.services.async_call(
            "camera", "turn_on", {"entity_id": "camera.ozmo_950_camera"}
        )
        await hass.async_block_till_done()

        state = hass.states.get("camera.ozmo_950_camera")
        assert state is not None
        assert state.state == "streaming"
        session_instance.start.assert_called_once()

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_turn_off_stops_session(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """Turning off camera stops the KVS session."""
        _, session_instance = mock_kvs_stream_session
        await hass.services.async_call(
            "camera", "turn_on", {"entity_id": "camera.ozmo_950_camera"}
        )
        await hass.async_block_till_done()

        await hass.services.async_call(
            "camera", "turn_off", {"entity_id": "camera.ozmo_950_camera"}
        )
        await hass.async_block_till_done()

        state = hass.states.get("camera.ozmo_950_camera")
        assert state is not None
        assert state.state != "streaming"
        session_instance.stop.assert_called_once()


class TestCameraImageRetrieval:
    """Tests for async_camera_image()."""

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_camera_image_returns_jpeg(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """async_camera_image returns the latest JPEG frame from the session."""
        _, session_instance = mock_kvs_stream_session
        session_instance.latest_jpeg = b"\xff\xd8\xff\xe0test"

        await hass.services.async_call(
            "camera", "turn_on", {"entity_id": "camera.ozmo_950_camera"}
        )
        await hass.async_block_till_done()

        image = await async_get_image(hass, "camera.ozmo_950_camera")
        assert image.content == b"\xff\xd8\xff\xe0test"

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_camera_image_none_before_first_frame(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """async_camera_image returns black placeholder when no frame received yet."""
        _, session_instance = mock_kvs_stream_session
        session_instance.latest_jpeg = None

        await hass.services.async_call(
            "camera", "turn_on", {"entity_id": "camera.ozmo_950_camera"}
        )
        await hass.async_block_till_done()

        image = await async_get_image(hass, "camera.ozmo_950_camera")
        # Should return the black JPEG placeholder, not raise
        assert image.content.startswith(b"\xff\xd8")

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_camera_off_returns_black_placeholder(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """Camera returns black placeholder when off (no active session)."""
        image = await async_get_image(hass, "camera.ozmo_950_camera")
        assert image.content.startswith(b"\xff\xd8")


class TestCameraPin:
    """Tests for PIN encoding and options flow integration."""

    def test_encode_pin_format(self) -> None:
        """encode_pin produces MD5(eco_ + digits)."""
        pin = "1234"
        expected = hashlib.md5(b"eco_1234").hexdigest()
        assert encode_pin(pin) == expected

    def test_encode_pin_empty_prefix(self) -> None:
        """encode_pin prefix is 'eco_'."""
        result = encode_pin("0000")
        assert result == hashlib.md5(b"eco_0000").hexdigest()

    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_options_flow_saves_pin(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Options flow stores encoded PIN in config entry options."""
        config_entry = hass.config_entries.async_entries(DOMAIN)[0]

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == "form"
        assert result["step_id"] == "camera_pins"

        did = config_entry.runtime_data.devices[0].device_info["did"]
        device_info = config_entry.runtime_data.devices[0].device_info
        field_key = _device_pin_field_key(device_info)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={field_key: "9999"},
        )
        assert result["type"] == "create_entry"

        stored_pins = config_entry.options.get(CONF_CAMERA_PINS, {})
        assert did in stored_pins
        assert stored_pins[did] == encode_pin("9999")

    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_options_flow_empty_pin_preserves_existing(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Leaving PIN blank preserves the previously saved hash."""
        config_entry = hass.config_entries.async_entries(DOMAIN)[0]
        device_info = config_entry.runtime_data.devices[0].device_info
        did = device_info["did"]

        # Pre-set a PIN in options
        hass.config_entries.async_update_entry(
            config_entry,
            options={CONF_CAMERA_PINS: {did: encode_pin("1111")}},
        )

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                _device_pin_field_key(device_info): ""
            },  # blank = keep existing
        )

        stored_pins = result["data"].get(CONF_CAMERA_PINS, {})
        assert stored_pins.get(did) == encode_pin("1111")


class TestCameraPinVerification:
    """Tests for PIN verification before stream start."""

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_pin_failure_prevents_stream(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
    ) -> None:
        """If PIN verification fails, the stream must not start."""
        _, session_instance = mock_kvs_stream_session

        with patch(
            "homeassistant.components.ecovacs.camera.verify_video_pwd",
            new_callable=AsyncMock,
            return_value={"ret": "fail"},
        ):
            await hass.services.async_call(
                "camera",
                "turn_on",
                {"entity_id": "camera.ozmo_950_camera"},
                blocking=True,
            )
            await hass.async_block_till_done()

        # session.start must NOT have been called
        session_instance.start.assert_not_called()

        # Camera state should remain idle (not streaming)
        state = hass.states.get("camera.ozmo_950_camera")
        assert state is not None
        assert state.state != "streaming"

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_pin_exception_prevents_stream(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
    ) -> None:
        """If PIN verification raises an exception, the stream must not start."""
        _, session_instance = mock_kvs_stream_session

        with patch(
            "homeassistant.components.ecovacs.camera.verify_video_pwd",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            await hass.services.async_call(
                "camera",
                "turn_on",
                {"entity_id": "camera.ozmo_950_camera"},
                blocking=True,
            )
            await hass.async_block_till_done()

        session_instance.start.assert_not_called()

        state = hass.states.get("camera.ozmo_950_camera")
        assert state is not None
        assert state.state != "streaming"
