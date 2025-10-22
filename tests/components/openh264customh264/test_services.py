"""Test OpenH264 integration services."""
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.components.camera import async_get_image

from custom_components.openh264customh264.const import DOMAIN


class TestCaptureSnapshotService:
    """Test capture_snapshot service."""

    @pytest.mark.asyncio
    async def test_capture_snapshot_success(self, hass: HomeAssistant, setup_integration, mock_camera_image, tmp_path):
        """Test successful snapshot capture."""
        # Mock the camera image
        with patch("homeassistant.components.camera.async_get_image", return_value=mock_camera_image):
            with patch("homeassistant.core.HomeAssistant.config") as mock_config:
                mock_config.path.return_value = str(tmp_path)
                
                await hass.services.async_call(
                    DOMAIN,
                    "capture_snapshot",
                    {
                        "entity_id": "camera.test_camera",
                        "filename": "test_snapshot.jpg",
                        "format": "jpg"
                    },
                    blocking=True,
                )
                
                # Verify file was created
                expected_file = tmp_path / "openh264" / "test_snapshot.jpg"
                assert expected_file.exists()

    @pytest.mark.asyncio
    async def test_capture_snapshot_with_template(self, hass: HomeAssistant, setup_integration, mock_camera_image, tmp_path):
        """Test snapshot capture with filename template."""
        with patch("homeassistant.components.camera.async_get_image", return_value=mock_camera_image):
            with patch("homeassistant.core.HomeAssistant.config") as mock_config:
                mock_config.path.return_value = str(tmp_path)
                
                await hass.services.async_call(
                    DOMAIN,
                    "capture_snapshot",
                    {
                        "entity_id": "camera.test_camera",
                        "filename": "{entity_id}_{timestamp}.jpg",
                        "format": "jpg"
                    },
                    blocking=True,
                )
                
                # Check that a file with camera name was created
                openh264_dir = tmp_path / "openh264"
                assert openh264_dir.exists()
                files = list(openh264_dir.glob("camera_test_camera_*.jpg"))
                assert len(files) == 1

    @pytest.mark.asyncio
    async def test_capture_snapshot_missing_entity_id(self, hass: HomeAssistant, setup_integration):
        """Test snapshot capture with missing entity_id."""
        with pytest.raises(HomeAssistantError, match="Missing required parameters"):
            await hass.services.async_call(
                DOMAIN,
                "capture_snapshot",
                {"filename": "test.jpg"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_capture_snapshot_camera_not_found(self, hass: HomeAssistant, setup_integration):
        """Test snapshot capture with non-existent camera."""
        with patch("homeassistant.components.camera.async_get_image", return_value=None):
            with pytest.raises(HomeAssistantError, match="Failed to get image"):
                await hass.services.async_call(
                    DOMAIN,
                    "capture_snapshot",
                    {
                        "entity_id": "camera.nonexistent",
                        "filename": "test.jpg"
                    },
                    blocking=True,
                )

    @pytest.mark.asyncio
    async def test_capture_snapshot_absolute_path(self, hass: HomeAssistant, setup_integration, mock_camera_image, tmp_path):
        """Test snapshot capture with absolute path."""
        absolute_path = tmp_path / "absolute_test.jpg"
        
        with patch("homeassistant.components.camera.async_get_image", return_value=mock_camera_image):
            await hass.services.async_call(
                DOMAIN,
                "capture_snapshot",
                {
                    "entity_id": "camera.test_camera",
                    "filename": str(absolute_path),
                    "format": "jpg"
                },
                blocking=True,
            )
            
            assert absolute_path.exists()


class TestRecordClipService:
    """Test record_clip service."""

    @pytest.mark.asyncio
    async def test_record_clip_success(self, hass: HomeAssistant, setup_integration, tmp_path):
        """Test successful clip recording."""
        # Mock the camera.record service
        with patch("homeassistant.core.HomeAssistant.services.async_call") as mock_call:
            with patch("homeassistant.core.HomeAssistant.config") as mock_config:
                mock_config.path.return_value = str(tmp_path)
                
                # Create mock output file
                output_file = tmp_path / "openh264" / "camera_test_camera_20231021_120000.mp4"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(b"mock video data")
                
                with patch("os.path.exists", return_value=True), \
                     patch("os.path.getsize", return_value=1024), \
                     patch("asyncio.sleep"):  # Skip the sleep delays
                    
                    await hass.services.async_call(
                        DOMAIN,
                        "record_clip",
                        {
                            "entity_id": "camera.test_camera",
                            "duration": 5,
                        },
                        blocking=True,
                    )
                    
                    # Verify camera.record was called
                    mock_call.assert_called()
                    call_args = mock_call.call_args
                    assert call_args[0] == ("camera", "record")

    @pytest.mark.asyncio
    async def test_record_clip_with_custom_filename(self, hass: HomeAssistant, setup_integration, tmp_path):
        """Test clip recording with custom filename."""
        with patch("homeassistant.core.HomeAssistant.services.async_call") as mock_call:
            with patch("homeassistant.core.HomeAssistant.config") as mock_config:
                mock_config.path.return_value = str(tmp_path)
                
                # Create mock output file
                output_file = tmp_path / "openh264" / "custom_video.mp4"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(b"mock video data")
                
                with patch("os.path.exists", return_value=True), \
                     patch("os.path.getsize", return_value=1024), \
                     patch("asyncio.sleep"):
                    
                    await hass.services.async_call(
                        DOMAIN,
                        "record_clip",
                        {
                            "entity_id": "camera.test_camera",
                            "filename": "custom_video.mp4",
                            "duration": 10,
                            "lookback": 5,
                        },
                        blocking=True,
                    )
                    
                    # Check call was made with correct parameters
                    call_args = mock_call.call_args[1]
                    assert call_args["duration"] == 10
                    assert call_args["lookback"] == 5

    @pytest.mark.asyncio
    async def test_record_clip_missing_entity_id(self, hass: HomeAssistant, setup_integration):
        """Test record clip with missing entity_id."""
        with pytest.raises(HomeAssistantError, match="Missing required parameter: entity_id"):
            await hass.services.async_call(
                DOMAIN,
                "record_clip",
                {"duration": 10},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_record_clip_stream_setup_failure(self, hass: HomeAssistant, setup_integration):
        """Test record clip when stream integration fails to load."""
        with patch("homeassistant.setup.async_setup_component", return_value=False):
            with pytest.raises(HomeAssistantError, match="Failed to load stream integration"):
                await hass.services.async_call(
                    DOMAIN,
                    "record_clip",
                    {"entity_id": "camera.test_camera"},
                    blocking=True,
                )

    @pytest.mark.asyncio
    async def test_record_clip_file_not_created(self, hass: HomeAssistant, setup_integration, tmp_path):
        """Test record clip when output file is not created."""
        with patch("homeassistant.core.HomeAssistant.services.async_call"):
            with patch("homeassistant.core.HomeAssistant.config") as mock_config:
                mock_config.path.return_value = str(tmp_path)
                
                with patch("os.path.exists", return_value=False), \
                     patch("asyncio.sleep"):
                    
                    with pytest.raises(HomeAssistantError, match="Recording file was not created"):
                        await hass.services.async_call(
                            DOMAIN,
                            "record_clip",
                            {"entity_id": "camera.test_camera"},
                            blocking=True,
                        )


class TestEncodeFileService:
    """Test encode_file service."""

    @pytest.mark.asyncio
    async def test_encode_file_ffmpeg_success(self, hass: HomeAssistant, setup_integration, tmp_path, 
                                            mock_ffmpeg_available, mock_subprocess_success):
        """Test successful file encoding with ffmpeg path."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"mock input video")
        
        output_file = tmp_path / "output.mp4"
        
        # Mock successful ffmpeg execution
        mock_subprocess_success.communicate.return_value = (b"", b"")
        
        with patch("os.path.exists", side_effect=lambda p: str(p) == str(input_file) or str(p) == str(output_file)), \
             patch("os.path.getsize", return_value=2048):
            
            await hass.services.async_call(
                DOMAIN,
                "encode_file",
                {
                    "input_path": str(input_file),
                    "output_path": str(output_file),
                    "bitrate": "1M",
                    "prefer_ffmpeg": True,
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_encode_file_shim_fallback(self, hass: HomeAssistant, setup_integration, tmp_path,
                                           mock_ffmpeg_available, mock_encoder):
        """Test file encoding with shim fallback."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"mock input video")
        
        # Mock ffmpeg failure for primary path, success for decoding
        mock_ffmpeg_failure = AsyncMock()
        mock_ffmpeg_failure.returncode = 1
        mock_ffmpeg_failure.communicate.return_value = (b"", b"libopenh264 not found")
        
        mock_probe_success = AsyncMock()
        mock_probe_success.returncode = 0
        mock_probe_success.communicate.return_value = (
            b"", 
            b"Stream #0:0: Video: h264, yuv420p, 1920x1080, 30 fps"
        )
        
        mock_decode_success = AsyncMock()
        mock_decode_success.stdout.readline = AsyncMock(side_effect=[
            b"YUV4MPEG2 W1920 H1080 F30:1 Ip A0:0 C420jpeg\n",
            b"FRAME\n",
            b"",  # EOF
        ])
        mock_decode_success.stdout.read = AsyncMock(return_value=b'\x00' * (1920 * 1080 * 3 // 2))
        mock_decode_success.wait = AsyncMock()
        
        def mock_subprocess(*args, **kwargs):
            if "encoders" in args[0]:
                return mock_ffmpeg_failure
            elif "-i" in args[0] and "-hide_banner" in args[0]:
                return mock_probe_success
            elif "yuv4mpegpipe" in args[0]:
                return mock_decode_success
            else:
                return mock_subprocess_success
        
        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess), \
             patch("custom_components.openh264customh264.encoder.OpenH264Encoder", return_value=mock_encoder), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("builtins.open", mock_open()):
            
            await hass.services.async_call(
                DOMAIN,
                "encode_file",
                {
                    "input_path": str(input_file),
                    "bitrate": "2M",
                    "prefer_ffmpeg": True,  # Will fall back to shim
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_encode_file_missing_input(self, hass: HomeAssistant, setup_integration):
        """Test encode_file with missing input_path."""
        with pytest.raises(HomeAssistantError, match="Missing required parameter: input_path"):
            await hass.services.async_call(
                DOMAIN,
                "encode_file",
                {"bitrate": "1M"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_encode_file_input_not_exists(self, hass: HomeAssistant, setup_integration):
        """Test encode_file with non-existent input file."""
        with pytest.raises(HomeAssistantError, match="Input file does not exist"):
            await hass.services.async_call(
                DOMAIN,
                "encode_file",
                {"input_path": "/nonexistent/file.mp4"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_encode_file_auto_output_path(self, hass: HomeAssistant, setup_integration, tmp_path):
        """Test encode_file with auto-generated output path."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"mock input video")
        
        with patch("homeassistant.core.HomeAssistant.config") as mock_config:
            mock_config.path.return_value = str(tmp_path)
            
            with patch("custom_components.openh264customh264.__init__._encode_with_ffmpeg_openh264", return_value=True):
                await hass.services.async_call(
                    DOMAIN,
                    "encode_file",
                    {"input_path": str(input_file)},
                    blocking=True,
                )

    @pytest.mark.asyncio
    async def test_encode_file_invalid_path(self, hass: HomeAssistant, setup_integration, tmp_path):
        """Test encode_file with invalid path components."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"mock input video")
        
        with pytest.raises(HomeAssistantError, match="Invalid file paths"):
            await hass.services.async_call(
                DOMAIN,
                "encode_file",
                {
                    "input_path": str(input_file),
                    "output_path": "../../../etc/passwd"
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_encode_file_ffmpeg_not_available(self, hass: HomeAssistant, setup_integration, tmp_path,
                                                   mock_ffmpeg_unavailable):
        """Test encode_file when ffmpeg is not available."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"mock input video")
        
        with pytest.raises(HomeAssistantError, match="ffmpeg is required for video decoding but not found"):
            await hass.services.async_call(
                DOMAIN,
                "encode_file",
                {
                    "input_path": str(input_file),
                    "prefer_ffmpeg": False  # Forces shim path
                },
                blocking=True,
            )


class TestServiceIntegration:
    """Test service integration aspects."""

    @pytest.mark.asyncio
    async def test_services_registered(self, hass: HomeAssistant, setup_integration):
        """Test that all services are properly registered."""
        services = hass.services.async_services()
        
        assert DOMAIN in services
        domain_services = services[DOMAIN]
        
        assert "capture_snapshot" in domain_services
        assert "record_clip" in domain_services
        assert "encode_file" in domain_services

    @pytest.mark.asyncio
    async def test_service_domain_control(self, hass: HomeAssistant, setup_integration):
        """Test that services have proper domain control."""
        # This tests that the @service.verify_domain_control decorator is applied
        # The actual domain control verification is handled by Home Assistant core
        
        # Test that we can call services (they should not raise domain control errors)
        with patch("homeassistant.components.camera.async_get_image"), \
             patch("homeassistant.core.HomeAssistant.config") as mock_config:
            
            mock_config.path.return_value = "/tmp"
            
            # Should not raise ServiceNotFound or domain control errors
            try:
                await hass.services.async_call(
                    DOMAIN,
                    "capture_snapshot",
                    {
                        "entity_id": "camera.test_camera",
                        "filename": "test.jpg"
                    },
                    blocking=True,
                )
            except HomeAssistantError:
                # Expected for missing camera, but not domain control error
                pass