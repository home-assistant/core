"""The OpenH264 Nedis Camera integration."""
from __future__ import annotations
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, ServiceCall
from homeassistant.const import Platform
from homeassistant.helpers import service
from .const import DOMAIN, LOGGER, CONF_LIB_PATH
from .encoder import OpenH264Encoder

PLATFORMS: list[Platform] = [Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenH264 Nedis Camera from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    data = dict(entry.data)
    options = dict(entry.options)
    
    # Initialize the OpenH264 encoder with default parameters
    lib_path = options.get(CONF_LIB_PATH) or data.get(CONF_LIB_PATH)
    # Create a default encoder instance for testing (640x480@30fps)
    # Real encoder will be created per camera based on actual dimensions
    try:
        encoder = OpenH264Encoder(width=640, height=480, fps=30, bitrate=2000000, lib_path=lib_path)
        LOGGER.info("OpenH264 encoder initialized successfully: %s", encoder.get_version())
    except Exception as e:
        LOGGER.warning("Failed to initialize OpenH264 encoder: %s. Services will work in fallback mode.", e)
        encoder = None
    
    # Store integration data
    hass.data[DOMAIN][entry.entry_id] = {
        "config": data,
        "options": options,
        "encoder": encoder
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services
    await _async_register_services(hass)
    
    LOGGER.info("OpenH264 Nedis Camera integration loaded for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        LOGGER.info("OpenH264 Nedis Camera integration unloaded for entry %s", entry.entry_id)
    
    return unload_ok


@callback
async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    LOGGER.debug("Reloading OpenH264 Nedis Camera integration due to options change")
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    
    @service.verify_domain_control(hass, DOMAIN)
    async def handle_encode_file(call: ServiceCall):
        """Handle encode_file service call."""
        import asyncio
        import os
        import shutil
        import subprocess
        from pathlib import Path
        from datetime import datetime
        from homeassistant.exceptions import HomeAssistantError
        
        input_path = call.data.get("input_path")
        output_path = call.data.get("output_path")
        bitrate = call.data.get("bitrate", "2M")
        fps = call.data.get("fps")
        gop = call.data.get("gop", 60)
        prefer_ffmpeg = call.data.get("prefer_ffmpeg", True)
        
        LOGGER.info("encode_file service called: %s -> %s (bitrate=%s, fps=%s, gop=%d, prefer_ffmpeg=%s)", 
                   input_path, output_path, bitrate, fps, gop, prefer_ffmpeg)
        
        # Validate input parameters
        if not input_path:
            LOGGER.error("Missing required parameter: input_path")
            raise HomeAssistantError("Missing required parameter: input_path")
        
        if not os.path.exists(input_path):
            LOGGER.error("Input file does not exist: %s", input_path)
            raise HomeAssistantError(f"Input file does not exist: {input_path}")
        
        # Generate output path if not provided
        if not output_path:
            input_path_obj = Path(input_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{input_path_obj.stem}_openh264_{timestamp}.mp4"
            output_dir = hass.config.path("www", "openh264")
            output_path = os.path.join(output_dir, output_filename)
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Validate file paths are within allowed locations
        try:
            # Basic path validation - reject obvious network paths or suspicious locations
            if any(part.startswith('..') for part in Path(input_path).parts):
                raise HomeAssistantError("Input path contains invalid components")
            if any(part.startswith('..') for part in Path(output_path).parts):
                raise HomeAssistantError("Output path contains invalid components")
        except Exception as e:
            LOGGER.error("Path validation failed: %s", e)
            raise HomeAssistantError(f"Invalid file paths: {e}")
        
        try:
            # Path A: Try ffmpeg with libopenh264 first (if preferred)
            if prefer_ffmpeg:
                success = await _encode_with_ffmpeg_openh264(
                    input_path, output_path, bitrate, fps, gop
                )
                if success:
                    LOGGER.info("File encoded successfully with ffmpeg+libopenh264: %s", output_path)
                    return
                else:
                    LOGGER.warning("ffmpeg+libopenh264 encoding failed, trying shim fallback")
            
            # Path B: Fallback to our shim with yuv4mpeg pipeline
            await _encode_with_shim(
                hass, input_path, output_path, bitrate, fps, gop
            )
            LOGGER.info("File encoded successfully with OpenH264 shim: %s", output_path)
            
        except Exception as e:
            LOGGER.error("Failed to encode file %s: %s", input_path, e)
            raise HomeAssistantError(f"Failed to encode file: {e}")
    
    async def _encode_with_ffmpeg_openh264(input_path: str, output_path: str, 
                                          bitrate: str, fps: int, gop: int) -> bool:
        """Try encoding with ffmpeg using libopenh264 encoder."""
        try:
            # Check if ffmpeg is available
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                LOGGER.warning("ffmpeg not found in PATH")
                return False
            
            # Check if libopenh264 encoder is available
            check_cmd = [ffmpeg_path, "-hide_banner", "-encoders"]
            result = await asyncio.create_subprocess_exec(
                *check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if b"libopenh264" not in stdout:
                LOGGER.warning("libopenh264 encoder not available in ffmpeg")
                return False
            
            LOGGER.info("Using ffmpeg with libopenh264 encoder")
            
            # Build ffmpeg command
            cmd = [
                ffmpeg_path,
                "-y",  # Overwrite output
                "-i", input_path,
                "-c:v", "libopenh264",
                "-b:v", bitrate,
                "-maxrate", bitrate,
                "-bufsize", f"{int(bitrate.rstrip('MmKk')) * 2}M" if bitrate.endswith(('M', 'm')) else f"{int(bitrate.rstrip('MmKk')) * 2000}k",
                "-pix_fmt", "yuv420p",
                "-profile:v", "baseline",
                "-level", "3.1",
                "-g", str(gop),
                "-c:a", "copy",  # Copy audio stream
                output_path
            ]
            
            # Add fps if specified
            if fps:
                cmd.extend(["-r", str(fps)])
            
            LOGGER.info("Running ffmpeg command: %s", ' '.join(cmd))
            
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)  # 10 min timeout
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                LOGGER.error("ffmpeg encoding timed out")
                return False
            
            if process.returncode != 0:
                LOGGER.error("ffmpeg failed with return code %d: %s", process.returncode, stderr.decode()[-1000:])
                return False
            
            # Verify output file was created and has reasonable size
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                return True
            else:
                LOGGER.error("ffmpeg output file is missing or too small")
                return False
                
        except Exception as e:
            LOGGER.error("ffmpeg encoding failed with exception: %s", e)
            return False
    
    async def _encode_with_shim(hass, input_path: str, output_path: str, 
                               bitrate: str, fps: int, gop: int) -> None:
        """Encode using our OpenH264 shim with yuv4mpeg pipeline."""
        LOGGER.info("Using OpenH264 shim encoding pipeline")
        
        # Check if ffmpeg is available for decoding
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise HomeAssistantError("ffmpeg is required for video decoding but not found")
        
        # Get encoder from integration data
        integration_data = hass.data.get(DOMAIN, {})
        if not integration_data:
            raise HomeAssistantError("Integration data not available")
        
        # Get video info first
        probe_cmd = [
            ffmpeg_path, "-i", input_path,
            "-hide_banner"
        ]
        
        probe_process = await asyncio.create_subprocess_exec(
            *probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await probe_process.communicate()
        
        # Parse video dimensions and fps from stderr (ffmpeg outputs info there)
        stderr_text = stderr.decode()
        width, height, source_fps = _parse_video_info(stderr_text)
        
        if not width or not height:
            raise HomeAssistantError("Could not determine video dimensions")
        
        # Use provided fps or source fps
        target_fps = fps or source_fps or 30
        
        # Convert bitrate to bps
        if isinstance(bitrate, str):
            if bitrate.lower().endswith('m'):
                bitrate_bps = int(float(bitrate[:-1]) * 1000000)
            elif bitrate.lower().endswith('k'):
                bitrate_bps = int(float(bitrate[:-1]) * 1000)
            else:
                bitrate_bps = int(bitrate)
        else:
            bitrate_bps = int(bitrate)
        
        LOGGER.info("Video info: %dx%d@%dfps, target bitrate: %d bps", width, height, target_fps, bitrate_bps)
        
        # Create encoder for this specific video
        from .encoder import OpenH264Encoder, OpenH264EncoderError
        
        try:
            encoder = OpenH264Encoder(
                width=width, height=height, fps=target_fps, 
                bitrate=bitrate_bps, keyint=gop, threads=2
            )
        except OpenH264EncoderError as e:
            raise HomeAssistantError(f"Failed to create OpenH264 encoder: {e}")
        
        if not encoder.available:
            encoder.close()
            raise HomeAssistantError("OpenH264 encoder is not available")
        
        try:
            # Decode to yuv4mpeg and encode with our shim
            await _process_video_with_shim(ffmpeg_path, input_path, output_path, encoder)
            
        finally:
            encoder.close()
    
    def _parse_video_info(stderr_text: str) -> tuple[int, int, int]:
        """Parse video width, height, and fps from ffmpeg stderr output."""
        import re
        
        width = height = fps = None
        
        # Look for video stream info like: "Stream #0:0: Video: h264, yuv420p, 1920x1080, 25 fps"
        video_match = re.search(r'Stream.*Video:.*?(\d+)x(\d+).*?(\d+(?:\.\d+)?)\s*fps', stderr_text)
        if video_match:
            width = int(video_match.group(1))
            height = int(video_match.group(2))
            fps = int(float(video_match.group(3)))
        
        return width, height, fps
    
    async def _process_video_with_shim(ffmpeg_path: str, input_path: str, 
                                      output_path: str, encoder) -> None:
        """Process video using yuv4mpeg pipeline with OpenH264 shim."""
        # Create temporary h264 file
        h264_temp_path = output_path + ".tmp.h264"
        
        try:
            # Start ffmpeg to decode to yuv4mpeg
            decode_cmd = [
                ffmpeg_path,
                "-i", input_path,
                "-f", "yuv4mpegpipe",
                "-pix_fmt", "yuv420p",
                "-"
            ]
            
            LOGGER.info("Starting video decode pipeline")
            
            decode_process = await asyncio.create_subprocess_exec(
                *decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            frame_count = 0
            total_encoded_size = 0
            
            with open(h264_temp_path, 'wb') as h264_file:
                # Read Y4M header
                header_line = await decode_process.stdout.readline()
                if not header_line.startswith(b'YUV4MPEG2'):
                    raise HomeAssistantError("Invalid YUV4MPEG stream")
                
                LOGGER.debug("Y4M header: %s", header_line.decode().strip())
                
                # Process frames
                while True:
                    # Read frame header
                    frame_header = await decode_process.stdout.readline()
                    if not frame_header:
                        break  # EOF
                    
                    if not frame_header.startswith(b'FRAME'):
                        LOGGER.warning("Unexpected frame header: %s", frame_header[:50])
                        continue
                    
                    # Calculate frame size (I420: Y + U/4 + V/4)
                    frame_size = encoder.width * encoder.height * 3 // 2
                    frame_data = await decode_process.stdout.read(frame_size)
                    
                    if len(frame_data) != frame_size:
                        LOGGER.warning("Short frame read: expected %d, got %d", frame_size, len(frame_data))
                        break
                    
                    # Encode frame
                    try:
                        encoded_data = encoder.encode_frame_sync(frame_data, "i420")
                        if encoded_data:
                            h264_file.write(encoded_data)
                            total_encoded_size += len(encoded_data)
                        
                        frame_count += 1
                        if frame_count % 30 == 0:  # Log every 30 frames (~1 second)
                            LOGGER.info("Processed %d frames, %d bytes encoded", frame_count, total_encoded_size)
                    
                    except Exception as e:
                        LOGGER.error("Frame encoding failed: %s", e)
                        raise HomeAssistantError(f"Frame encoding failed: {e}")
                
                # Wait for decode process to finish
                await decode_process.wait()
                
            LOGGER.info("Encoded %d frames to H.264 (%d bytes total)", frame_count, total_encoded_size)
            
            if total_encoded_size == 0:
                raise HomeAssistantError("No encoded data produced")
            
            # Wrap H.264 stream in MP4 container
            await _wrap_h264_in_mp4(ffmpeg_path, h264_temp_path, output_path, encoder.fps)
            
        finally:
            # Clean up temporary file
            if os.path.exists(h264_temp_path):
                os.unlink(h264_temp_path)
    
    async def _wrap_h264_in_mp4(ffmpeg_path: str, h264_path: str, output_path: str, fps: int) -> None:
        """Wrap raw H.264 stream in MP4 container."""
        cmd = [
            ffmpeg_path,
            "-y",  # Overwrite output
            "-f", "h264",
            "-r", str(fps),  # Set frame rate
            "-i", h264_path,
            "-c", "copy",  # Copy without re-encoding
            "-movflags", "faststart",  # Optimize for streaming
            output_path
        ]
        
        LOGGER.info("Wrapping H.264 in MP4 container")
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            LOGGER.error("MP4 wrapping failed: %s", stderr.decode()[-500:])
            raise HomeAssistantError("Failed to create MP4 container")
        
        # Verify output
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            raise HomeAssistantError("MP4 output file is missing or too small")

    @service.verify_domain_control(hass, DOMAIN)  
    async def handle_capture_snapshot(call: ServiceCall):
        """Handle capture_snapshot service call."""
        import os
        import tempfile
        from datetime import datetime
        from homeassistant.components.camera import async_get_image
        from homeassistant.exceptions import HomeAssistantError
        
        entity_id = call.data.get("entity_id")
        filename = call.data.get("filename")
        image_format = call.data.get("format", "jpg").lower()
        
        LOGGER.info("capture_snapshot service called: %s -> %s (format: %s)", entity_id, filename, image_format)
        
        if not entity_id or not filename:
            LOGGER.error("Missing required parameters: entity_id and filename")
            raise HomeAssistantError("Missing required parameters: entity_id and filename")
        
        try:
            # Get camera image
            camera_image = await async_get_image(hass, entity_id)
            if not camera_image:
                raise HomeAssistantError(f"Failed to get image from camera {entity_id}")
            
            # Process filename template
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            processed_filename = filename.format(
                entity_id=entity_id.replace(".", "_"),
                timestamp=timestamp
            )
            
            # Resolve path - if relative, put in www/openh264
            if not os.path.isabs(processed_filename):
                output_dir = hass.config.path("www", "openh264")
                processed_filename = os.path.join(output_dir, processed_filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(processed_filename), exist_ok=True)
            
            # Write image data atomically
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, 
                                           dir=os.path.dirname(processed_filename),
                                           suffix=f'.tmp.{image_format}') as tmp_file:
                tmp_file.write(camera_image.content)
                tmp_path = tmp_file.name
            
            # Atomic rename
            os.rename(tmp_path, processed_filename)
            os.chmod(processed_filename, 0o644)
            
            LOGGER.info("Snapshot saved successfully: %s (%d bytes)", processed_filename, len(camera_image.content))
            
        except Exception as e:
            LOGGER.error("Failed to capture snapshot from %s: %s", entity_id, e)
            raise HomeAssistantError(f"Failed to capture snapshot: {e}")

    @service.verify_domain_control(hass, DOMAIN)
    async def handle_record_clip(call: ServiceCall):
        """Handle record_clip service call."""
        import asyncio
        import os
        from datetime import datetime
        from homeassistant.exceptions import HomeAssistantError
        from homeassistant.helpers import service as service_helper
        
        entity_id = call.data.get("entity_id")
        filename = call.data.get("filename")
        duration = call.data.get("duration", 10)
        lookback = call.data.get("lookback", 0)
        
        LOGGER.info("record_clip service called: %s -> %s (%ds, lookback=%ds)", 
                   entity_id, filename, duration, lookback)
        
        if not entity_id:
            LOGGER.error("Missing required parameter: entity_id")
            raise HomeAssistantError("Missing required parameter: entity_id")
        
        try:
            # Process filename template if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_entity_id = entity_id.replace(".", "_")
                filename = f"{safe_entity_id}_{timestamp}.mp4"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = filename.format(
                    entity_id=entity_id.replace(".", "_"),
                    timestamp=timestamp
                )
            
            # Resolve path - if relative, put in www/openh264
            if not os.path.isabs(filename):
                output_dir = hass.config.path("www", "openh264")
                filename = os.path.join(output_dir, filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Ensure stream integration is loaded
            if "stream" not in hass.config.components:
                LOGGER.info("Loading stream integration for recording")
                from homeassistant.setup import async_setup_component
                success = await async_setup_component(hass, "stream", hass.config)
                if not success:
                    raise HomeAssistantError("Failed to load stream integration")
            
            # Call camera.record service
            record_data = {
                "entity_id": entity_id,
                "filename": filename,
                "duration": duration,
            }
            if lookback > 0:
                record_data["lookback"] = lookback
            
            LOGGER.info("Starting recording with data: %s", record_data)
            await hass.services.async_call("camera", "record", record_data, blocking=True)
            
            # Wait a bit and verify file was created
            await asyncio.sleep(2)  # Give the service time to start
            
            # Wait for file to appear and stabilize
            max_wait = duration + 30  # Duration plus 30s grace period
            start_time = asyncio.get_event_loop().time()
            last_size = -1
            stable_count = 0
            
            while (asyncio.get_event_loop().time() - start_time) < max_wait:
                if os.path.exists(filename):
                    current_size = os.path.getsize(filename)
                    if current_size == last_size and current_size > 0:
                        stable_count += 1
                        if stable_count >= 3:  # Stable for 3 checks (6 seconds)
                            break
                    else:
                        stable_count = 0
                    last_size = current_size
                    LOGGER.debug("Recording in progress: %s bytes", current_size)
                
                await asyncio.sleep(2)
            
            if not os.path.exists(filename):
                raise HomeAssistantError(f"Recording file was not created: {filename}")
            
            final_size = os.path.getsize(filename)
            if final_size == 0:
                raise HomeAssistantError(f"Recording file is empty: {filename}")
            
            LOGGER.info("Recording completed successfully: %s (%d bytes)", filename, final_size)
            
        except Exception as e:
            LOGGER.error("Failed to record clip from %s: %s", entity_id, e)
            raise HomeAssistantError(f"Failed to record clip: {e}")

    # Register all services
    hass.services.async_register(DOMAIN, "encode_file", handle_encode_file)
    hass.services.async_register(DOMAIN, "capture_snapshot", handle_capture_snapshot)  
    hass.services.async_register(DOMAIN, "record_clip", handle_record_clip)