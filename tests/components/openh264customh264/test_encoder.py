"""Test OpenH264 encoder functionality."""
import pytest
from unittest.mock import MagicMock, patch, mock_open
import ctypes

from custom_components.openh264customh264.encoder import (
    OpenH264Encoder,
    OpenH264EncoderError,
    H264_SUCCESS,
    H264_ERROR_INVALID_PARAM,
)


class TestOpenH264Encoder:
    """Test OpenH264Encoder class."""

    def test_encoder_creation_success(self):
        """Test successful encoder creation."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678  # Mock handle
            mock_lib.h264_encoder_version.return_value = b"Test v1.0"
            mock_load.return_value = mock_lib
            
            with patch("pathlib.Path.exists", return_value=True):
                encoder = OpenH264Encoder(640, 480, 30, 2000000)
                
                assert encoder.available
                assert encoder.width == 640
                assert encoder.height == 480
                assert encoder.fps == 30
                assert encoder.bitrate == 2000000

    def test_encoder_creation_library_not_found(self):
        """Test encoder creation when library is not found."""
        with patch("pathlib.Path.exists", return_value=False), \
             patch("os.path.exists", return_value=False), \
             patch("subprocess.run") as mock_run:
            
            mock_run.return_value.returncode = 1  # Brew command fails
            
            with pytest.raises(OpenH264EncoderError, match="OpenH264 library not found"):
                OpenH264Encoder(640, 480)

    def test_encoder_creation_handle_failure(self):
        """Test encoder creation when handle creation fails."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0  # NULL handle
            mock_load.return_value = mock_lib
            
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(OpenH264EncoderError, match="Failed to create encoder"):
                    OpenH264Encoder(640, 480)

    def test_encode_frame_sync_rgb(self):
        """Test synchronous frame encoding with RGB input."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_lib.h264_encoder_encode.return_value = H264_SUCCESS
            mock_load.return_value = mock_lib
            
            # Mock ctypes functions
            with patch("ctypes.create_string_buffer") as mock_buffer, \
                 patch("ctypes.byref"), \
                 patch("pathlib.Path.exists", return_value=True):
                
                # Create mock output buffer
                mock_output_buffer = MagicMock()
                mock_output_buffer.raw = b'\x00\x00\x00\x01\x67\x42\x00\x1f'  # Mock H.264 data
                mock_buffer.return_value = mock_output_buffer
                
                encoder = OpenH264Encoder(4, 4, 30, 1000000)  # Small size for testing
                
                # Create minimal RGB data (4x4 RGB = 48 bytes)
                rgb_data = b'\xff' * 48
                
                with patch.object(encoder, '_rgb_to_i420', return_value=(b'\xff' * 16, b'\x80' * 4, b'\x80' * 4)):
                    result = encoder.encode_frame_sync(rgb_data, "rgb")
                    
                    assert result == b'\x00\x00\x00\x01\x67\x42\x00\x1f'
                    mock_lib.h264_encoder_encode.assert_called_once()

    def test_encode_frame_sync_i420(self):
        """Test synchronous frame encoding with I420 input."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_lib.h264_encoder_encode.return_value = H264_SUCCESS
            mock_load.return_value = mock_lib
            
            with patch("ctypes.create_string_buffer") as mock_buffer, \
                 patch("ctypes.byref"), \
                 patch("pathlib.Path.exists", return_value=True):
                
                mock_output_buffer = MagicMock()
                mock_output_buffer.raw = b'\x00\x00\x00\x01\x67\x42\x00\x1f'
                mock_buffer.return_value = mock_output_buffer
                
                encoder = OpenH264Encoder(4, 4, 30, 1000000)
                
                # I420 data for 4x4 image: Y(16) + U(4) + V(4) = 24 bytes
                i420_data = b'\xff' * 24
                
                result = encoder.encode_frame_sync(i420_data, "i420")
                
                assert result == b'\x00\x00\x00\x01\x67\x42\x00\x1f'

    def test_encode_frame_invalid_format(self):
        """Test encoding with invalid input format."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_load.return_value = mock_lib
            
            with patch("pathlib.Path.exists", return_value=True):
                encoder = OpenH264Encoder(640, 480)
                
                with pytest.raises(OpenH264EncoderError, match="Unsupported input format"):
                    encoder.encode_frame_sync(b"test", "invalid_format")

    def test_encode_frame_wrong_size(self):
        """Test encoding with wrong data size."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_load.return_value = mock_lib
            
            with patch("pathlib.Path.exists", return_value=True):
                encoder = OpenH264Encoder(640, 480)
                
                # Wrong size RGB data
                wrong_size_data = b'\xff' * 100  # Should be 640*480*3
                
                with pytest.raises(OpenH264EncoderError, match="RGB data size mismatch"):
                    encoder.encode_frame_sync(wrong_size_data, "rgb")

    def test_encode_frame_encoder_error(self):
        """Test handling of encoder errors."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_lib.h264_encoder_encode.return_value = H264_ERROR_INVALID_PARAM
            mock_load.return_value = mock_lib
            
            with patch("ctypes.create_string_buffer"), \
                 patch("ctypes.byref"), \
                 patch("pathlib.Path.exists", return_value=True):
                
                encoder = OpenH264Encoder(4, 4, 30, 1000000)
                
                i420_data = b'\xff' * 24
                
                with pytest.raises(OpenH264EncoderError, match="Encoding failed: Invalid parameters"):
                    encoder.encode_frame_sync(i420_data, "i420")

    def test_force_keyframe(self):
        """Test forcing keyframe."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_lib.h264_encoder_force_idr.return_value = H264_SUCCESS
            mock_load.return_value = mock_lib
            
            with patch("pathlib.Path.exists", return_value=True):
                encoder = OpenH264Encoder(640, 480)
                
                encoder.force_keyframe()
                
                mock_lib.h264_encoder_force_idr.assert_called_once_with(0x12345678)

    def test_encoder_close(self):
        """Test encoder cleanup."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_load.return_value = mock_lib
            
            with patch("pathlib.Path.exists", return_value=True):
                encoder = OpenH264Encoder(640, 480)
                
                encoder.close()
                
                mock_lib.h264_encoder_destroy.assert_called_once_with(0x12345678)
                assert encoder._encoder_handle is None

    @pytest.mark.asyncio
    async def test_encode_frame_async(self):
        """Test asynchronous frame encoding."""
        with patch("custom_components.openh264customh264.encoder.ctypes.cdll.LoadLibrary") as mock_load:
            mock_lib = MagicMock()
            mock_lib.h264_encoder_create.return_value = 0x12345678
            mock_lib.h264_encoder_encode.return_value = H264_SUCCESS
            mock_load.return_value = mock_lib
            
            with patch("ctypes.create_string_buffer") as mock_buffer, \
                 patch("ctypes.byref"), \
                 patch("pathlib.Path.exists", return_value=True):
                
                mock_output_buffer = MagicMock()
                mock_output_buffer.raw = b'\x00\x00\x00\x01\x67\x42\x00\x1f'
                mock_buffer.return_value = mock_output_buffer
                
                encoder = OpenH264Encoder(4, 4, 30, 1000000)
                
                i420_data = b'\xff' * 24
                
                result = await encoder.encode_frame(i420_data, "i420")
                
                assert result == b'\x00\x00\x00\x01\x67\x42\x00\x1f'