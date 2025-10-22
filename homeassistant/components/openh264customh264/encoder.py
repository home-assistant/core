"""OpenH264 encoder wrapper."""
from __future__ import annotations
import asyncio
import ctypes
from ctypes import POINTER, c_int, c_uint8, c_void_p
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from .const import LOGGER

# Error codes from the shim
H264_SUCCESS = 0
H264_ERROR_INVALID_PARAM = -1
H264_ERROR_MEMORY_ALLOC = -2
H264_ERROR_ENCODER_INIT = -3
H264_ERROR_ENCODE_FAILED = -4
H264_ERROR_NULL_ENCODER = -5
H264_ERROR_OUTPUT_BUFFER_TOO_SMALL = -6

ERROR_MESSAGES = {
    H264_ERROR_INVALID_PARAM: "Invalid parameters",
    H264_ERROR_MEMORY_ALLOC: "Memory allocation failed",
    H264_ERROR_ENCODER_INIT: "Encoder initialization failed",
    H264_ERROR_ENCODE_FAILED: "Encoding failed",
    H264_ERROR_NULL_ENCODER: "Null encoder handle",
    H264_ERROR_OUTPUT_BUFFER_TOO_SMALL: "Output buffer too small",
}


class OpenH264EncoderError(Exception):
    """Exception raised by OpenH264Encoder."""
    pass


class OpenH264Encoder:
    """OpenH264 encoder wrapper class with real ctypes bindings."""
    
    def __init__(self, width: int, height: int, fps: int = 30, bitrate: int = 2000000, 
                 keyint: int = 60, threads: int = 1, lib_path: Optional[str] = None):
        """Initialize the encoder.
        
        Args:
            width: Video width in pixels
            height: Video height in pixels  
            fps: Frame rate (frames per second)
            bitrate: Target bitrate in bits per second
            keyint: Keyframe interval (GOP size)
            threads: Number of threads to use
            lib_path: Optional path to the shim library
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.keyint = keyint
        self.threads = threads
        
        self._lib = None
        self._encoder_handle = None
        self._lock = asyncio.Lock()
        
        # Load the library
        self._load_library(lib_path)
        
        # Create encoder
        if self._lib:
            self._create_encoder()
    
    def _load_library(self, lib_path: Optional[str] = None) -> None:
        """Load the OpenH264 shim library."""
        search_paths = []
        
        if lib_path:
            search_paths.append(lib_path)
        
        # Add our built shim
        current_dir = Path(__file__).parent
        shim_path = current_dir / "bin" / "macos" / "libopenh264shim.dylib"
        if shim_path.exists():
            search_paths.append(str(shim_path))
        
        # Try Homebrew locations
        try:
            import subprocess
            result = subprocess.run(["brew", "--prefix", "openh264"], 
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0:
                homebrew_path = result.stdout.strip()
                search_paths.append(f"{homebrew_path}/lib/libopenh264.dylib")
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        
        # Standard system locations
        search_paths.extend([
            "/opt/homebrew/lib/libopenh264.dylib",
            "/usr/local/lib/libopenh264.dylib",
            "/usr/lib/libopenh264.so",
        ])
        
        for path in search_paths:
            if os.path.exists(path):
                try:
                    self._lib = ctypes.cdll.LoadLibrary(path)
                    LOGGER.info("Loaded OpenH264 library from %s", path)
                    self._setup_function_prototypes()
                    return
                except OSError as e:
                    LOGGER.warning("Failed to load library %s: %s", path, e)
                    continue
        
        LOGGER.error("Could not load OpenH264 library. Install with: brew install openh264")
        raise OpenH264EncoderError("OpenH264 library not found")
    
    def _setup_function_prototypes(self) -> None:
        """Set up ctypes function prototypes."""
        if not self._lib:
            return
        
        # h264_encoder_create(width, height, fps, bitrate, keyint, threads)
        self._lib.h264_encoder_create.restype = c_void_p
        self._lib.h264_encoder_create.argtypes = [c_int, c_int, c_int, c_int, c_int, c_int]
        
        # h264_encoder_encode(encoder, y, u, v, stride_y, stride_u, stride_v, 
        #                    out_buf, out_buf_size, out_size, is_keyframe)
        self._lib.h264_encoder_encode.restype = c_int
        self._lib.h264_encoder_encode.argtypes = [
            c_void_p, c_void_p, c_void_p, c_void_p, 
            c_int, c_int, c_int, c_void_p, c_int, 
            POINTER(c_int), POINTER(c_int)
        ]
        
        # h264_encoder_destroy(encoder)
        self._lib.h264_encoder_destroy.restype = None
        self._lib.h264_encoder_destroy.argtypes = [c_void_p]
        
        # h264_encoder_force_idr(encoder)
        self._lib.h264_encoder_force_idr.restype = c_int
        self._lib.h264_encoder_force_idr.argtypes = [c_void_p]
        
        # h264_encoder_version()
        self._lib.h264_encoder_version.restype = ctypes.c_char_p
        self._lib.h264_encoder_version.argtypes = []
    
    def _create_encoder(self) -> None:
        """Create the encoder instance."""
        if not self._lib:
            raise OpenH264EncoderError("Library not loaded")
        
        self._encoder_handle = self._lib.h264_encoder_create(
            self.width, self.height, self.fps, self.bitrate, self.keyint, self.threads
        )
        
        if not self._encoder_handle:
            raise OpenH264EncoderError("Failed to create encoder")
        
        LOGGER.info("Created OpenH264 encoder %dx%d@%dfps, bitrate=%d, keyint=%d", 
                   self.width, self.height, self.fps, self.bitrate, self.keyint)
    
    @property
    def available(self) -> bool:
        """Check if OpenH264 encoder is available and initialized."""
        return self._lib is not None and self._encoder_handle is not None
    
    def get_version(self) -> str:
        """Get encoder version string."""
        if not self._lib:
            return "Library not loaded"
        try:
            version_bytes = self._lib.h264_encoder_version()
            return version_bytes.decode('utf-8')
        except Exception as e:
            return f"Version unavailable: {e}"
    
    def force_keyframe(self) -> None:
        """Force the next frame to be a keyframe."""
        if not self.available:
            raise OpenH264EncoderError("Encoder not available")
        
        result = self._lib.h264_encoder_force_idr(self._encoder_handle)
        if result != H264_SUCCESS:
            error_msg = ERROR_MESSAGES.get(result, f"Unknown error {result}")
            raise OpenH264EncoderError(f"Failed to force IDR: {error_msg}")
    
    def _rgb_to_i420(self, rgb_data: bytes, width: int, height: int) -> Tuple[bytes, bytes, bytes]:
        """Convert RGB data to I420 planar format."""
        if NUMPY_AVAILABLE:
            return self._rgb_to_i420_numpy(rgb_data, width, height)
        elif PIL_AVAILABLE:
            return self._rgb_to_i420_pil(rgb_data, width, height)
        else:
            raise OpenH264EncoderError("RGB conversion requires PIL or numpy")
    
    def _rgb_to_i420_numpy(self, rgb_data: bytes, width: int, height: int) -> Tuple[bytes, bytes, bytes]:
        """Convert RGB to I420 using numpy (faster)."""
        # Convert RGB bytes to numpy array
        rgb_array = np.frombuffer(rgb_data, dtype=np.uint8).reshape((height, width, 3))
        
        # Convert RGB to YUV using ITU-R BT.601 coefficients
        rgb_f = rgb_array.astype(np.float32)
        y = 0.299 * rgb_f[:, :, 0] + 0.587 * rgb_f[:, :, 1] + 0.114 * rgb_f[:, :, 2]
        u = -0.169 * rgb_f[:, :, 0] - 0.331 * rgb_f[:, :, 1] + 0.500 * rgb_f[:, :, 2] + 128
        v = 0.500 * rgb_f[:, :, 0] - 0.419 * rgb_f[:, :, 1] - 0.081 * rgb_f[:, :, 2] + 128
        
        # Clip to valid range
        y = np.clip(y, 0, 255).astype(np.uint8)
        u = np.clip(u, 0, 255).astype(np.uint8) 
        v = np.clip(v, 0, 255).astype(np.uint8)
        
        # Subsample U and V to 4:2:0
        u_sub = u[::2, ::2]  # Take every 2nd pixel in both dimensions
        v_sub = v[::2, ::2]
        
        return y.tobytes(), u_sub.tobytes(), v_sub.tobytes()
    
    def _rgb_to_i420_pil(self, rgb_data: bytes, width: int, height: int) -> Tuple[bytes, bytes, bytes]:
        """Convert RGB to I420 using PIL (slower but more compatible)."""
        # Create PIL image from RGB data
        img = Image.frombuffer("RGB", (width, height), rgb_data, "raw", "RGB", 0, 1)
        
        # Convert to YCbCr
        ycbcr_img = img.convert("YCbCr")
        
        # Split into Y, Cb, Cr planes
        y_img, cb_img, cr_img = ycbcr_img.split()
        
        # Subsample Cb and Cr to 4:2:0
        cb_sub = cb_img.resize((width // 2, height // 2), Image.BILINEAR)
        cr_sub = cr_img.resize((width // 2, height // 2), Image.BILINEAR)
        
        return y_img.tobytes(), cb_sub.tobytes(), cr_sub.tobytes()
    
    async def encode_frame(self, image_data: bytes, input_format: str = "rgb") -> bytes:
        """Encode a frame to H.264.
        
        Args:
            image_data: Raw image data
            input_format: Input format ("rgb", "bgr", or "i420")
        
        Returns:
            Encoded H.264 data as bytes
        """
        async with self._lock:
            return self._encode_frame_sync(image_data, input_format)
    
    def _encode_frame_sync(self, image_data: bytes, input_format: str = "rgb") -> bytes:
        """Synchronous frame encoding implementation."""
        if not self.available:
            raise OpenH264EncoderError("Encoder not available")
        
        # Convert input to I420 if needed
        if input_format.lower() == "i420":
            # Assume data is already in I420 planar format
            expected_size = self.width * self.height * 3 // 2
            if len(image_data) != expected_size:
                raise OpenH264EncoderError(f"I420 data size mismatch: expected {expected_size}, got {len(image_data)}")
            
            y_size = self.width * self.height
            uv_size = y_size // 4
            y_plane = image_data[:y_size]
            u_plane = image_data[y_size:y_size + uv_size]
            v_plane = image_data[y_size + uv_size:y_size + 2 * uv_size]
        elif input_format.lower() in ("rgb", "bgr"):
            expected_size = self.width * self.height * 3
            if len(image_data) != expected_size:
                raise OpenH264EncoderError(f"RGB data size mismatch: expected {expected_size}, got {len(image_data)}")
            
            if input_format.lower() == "bgr":
                # Convert BGR to RGB
                rgb_data = bytes(image_data[i:i+3][::-1] for i in range(0, len(image_data), 3))
            else:
                rgb_data = image_data
            
            y_plane, u_plane, v_plane = self._rgb_to_i420(rgb_data, self.width, self.height)
        else:
            raise OpenH264EncoderError(f"Unsupported input format: {input_format}")
        
        # Prepare input buffers
        y_buffer = ctypes.create_string_buffer(y_plane)
        u_buffer = ctypes.create_string_buffer(u_plane)
        v_buffer = ctypes.create_string_buffer(v_plane)
        
        # Prepare output buffer (allocate generous size)
        output_size = max(1024 * 1024, self.width * self.height)  # 1MB or frame size, whichever is larger
        output_buffer = ctypes.create_string_buffer(output_size)
        
        # Output parameters
        actual_size = c_int(0)
        is_keyframe = c_int(0)
        
        # Calculate strides
        stride_y = self.width
        stride_u = self.width // 2
        stride_v = self.width // 2
        
        # Call encoder
        result = self._lib.h264_encoder_encode(
            self._encoder_handle,
            ctypes.cast(y_buffer, c_void_p),
            ctypes.cast(u_buffer, c_void_p),
            ctypes.cast(v_buffer, c_void_p),
            stride_y, stride_u, stride_v,
            ctypes.cast(output_buffer, c_void_p),
            output_size,
            ctypes.byref(actual_size),
            ctypes.byref(is_keyframe)
        )
        
        if result != H264_SUCCESS:
            error_msg = ERROR_MESSAGES.get(result, f"Unknown error {result}")
            raise OpenH264EncoderError(f"Encoding failed: {error_msg}")
        
        if actual_size.value == 0:
            LOGGER.debug("Frame was skipped by encoder")
            return b''
        
        LOGGER.debug("Encoded frame: %d bytes, keyframe=%s", actual_size.value, bool(is_keyframe.value))
        return output_buffer.raw[:actual_size.value]
    
    def encode_frame_sync(self, image_data: bytes, input_format: str = "rgb") -> bytes:
        """Synchronous version of encode_frame for compatibility."""
        return self._encode_frame_sync(image_data, input_format)
    
    def close(self) -> None:
        """Close the encoder and free resources."""
        if self._encoder_handle and self._lib:
            self._lib.h264_encoder_destroy(self._encoder_handle)
            self._encoder_handle = None
            LOGGER.info("Closed OpenH264 encoder")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.close()
