# OpenH264 Nedis Camera Integration

A custom Home Assistant integration for Nedis security cameras with OpenH264 video processing capabilities.

## Features

- **Dual Operation Modes**:
  - **Camera Entity Proxy**: Proxy an existing Home Assistant camera entity with OpenH264 processing
  - **Direct URL**: Connect directly to camera RTSP streams and snapshot URLs

- **OpenH264 Support**: Optional H.264 video encoding using Cisco's OpenH264 library
- **UI Configuration**: Complete configuration flow through Home Assistant's UI
- **Services**: Custom services for encoding, snapshots, and recording
- **Diagnostics**: Built-in diagnostics support for troubleshooting

## Installation

### Prerequisites

**OpenH264 Library (Optional)**:
- macOS: `brew install openh264`
- Ubuntu/Debian: `sudo apt install libopenh264-dev` (if available)
- Other systems: Install from [Cisco's OpenH264 releases](https://github.com/cisco/openh264/releases)

**FFmpeg (Recommended)**:
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`

### Integration Installation

1. Copy the `openh264customh264` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "OpenH264 Nedis Camera" and follow the setup wizard

## Configuration

### Mode 1: Camera Entity Proxy
- **Name**: Display name for the camera
- **Source Type**: Select "camera_entity" 
- **Camera entity_id**: Existing camera entity to proxy (e.g., `camera.nedis_cam_01`)
- **Path to libopenh264**: Optional path to OpenH264 library
- **License Agreement**: Accept Cisco OpenH264 license if using auto-download

### Mode 2: Direct URL
- **Name**: Display name for the camera
- **Source Type**: Select "stream_url"
- **RTSP/Stream URL**: Direct RTSP stream URL (e.g., `rtsp://192.168.1.100:554/stream1`)
- **Snapshot URL**: Direct snapshot URL (e.g., `http://192.168.1.100/snapshot.jpg`)
- **Path to libopenh264**: Optional path to OpenH264 library
- **License Agreement**: Accept Cisco OpenH264 license if using auto-download

### Common Nedis Camera URLs
- **RTSP Stream**: `rtsp://[IP]:[PORT]/[stream_path]`
  - Default ports: 554 (RTSP), 8554 (alternative)
  - Common paths: `/stream1`, `/live/ch00_1`, `/h264Preview_01_sub`
- **Snapshots**: `http://[IP]/snapshot.jpg` or `http://[IP]/cgi-bin/snapshot.cgi`

## Services

### `openh264customh264.encode_file`
Encode a video file using OpenH264.
- **input_path**: Path to input video file
- **output_path**: Path for encoded output file

### `openh264customh264.capture_snapshot`
Capture a snapshot from the camera.
- **entity_id**: Camera entity to capture from
- **filename**: Output file path

### `openh264customh264.record_clip`
Record a video clip from the camera.
- **entity_id**: Camera entity to record from
- **filename**: Output file path
- **duration**: Recording duration in seconds (1-300)

## Troubleshooting

### Camera Not Available
- **Camera Entity Mode**: Verify the source camera entity exists and is available
- **URL Mode**: Check network connectivity to camera IP/URLs
- **Authentication**: Ensure camera credentials are embedded in URLs if required

### OpenH264 Issues
- **Library Not Found**: Check the library path in integration options
- **Permission Errors**: Ensure Home Assistant has read access to the library file
- **Version Compatibility**: Use OpenH264 v2.0+ for best compatibility

### Network Issues
- **Timeouts**: Default timeout is 10 seconds; check network latency to camera
- **Firewall**: Ensure RTSP (554) and HTTP ports are accessible
- **Bandwidth**: RTSP streams require sufficient bandwidth for smooth operation

### Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.openh264customh264: debug
```

## License Notes

This integration can optionally use Cisco's OpenH264 library, which is subject to Cisco's license terms. The library is not redistributed with this integration. Users must:

1. Accept Cisco's OpenH264 license terms
2. Install the library separately or enable auto-download (when available)
3. Comply with all applicable license requirements

## Development

This integration provides a foundation for OpenH264-based camera processing. Current OpenH264 integration is at stub level - full encoder bindings are planned for future releases.

### Extending for Other Vendors
The integration is designed to be extensible beyond Nedis cameras. The URL patterns and authentication methods can be adapted for other camera brands.

## Version History

- **v0.1.0**: Initial release with dual-mode support, UI config flow, basic services, and OpenH264 stubs