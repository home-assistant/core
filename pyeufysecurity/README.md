# pyeufysecurity

Python library for Eufy Security cameras and devices.

Based on [eufy-security-client](https://github.com/bropat/eufy-security-client) by bropat.

## Installation

```bash
pip install pyeufysecurity
```

## Usage

```python
import asyncio
import aiohttp
from pyeufysecurity import async_login

async def main():
    async with aiohttp.ClientSession() as session:
        api = await async_login(
            email="your-email@example.com",
            password="your-password",
            session=session,
        )

        print(f"Found {len(api.cameras)} cameras")

        for camera in api.cameras.values():
            print(f"Camera: {camera.name} ({camera.model})")
            print(f"  Serial: {camera.serial}")
            print(f"  Image URL: {camera.last_camera_image_url}")

            # Start RTSP stream
            stream_url = await camera.async_start_stream()
            print(f"  Stream URL: {stream_url}")

            # Stop stream when done
            await camera.async_stop_stream()

asyncio.run(main())
```

## Features

- Async authentication with Eufy Security cloud API using v2 encrypted protocol
- ECDH key exchange for secure communication
- CAPTCHA support for login verification
- Automatic token refresh when expired
- Automatic domain switching for regional API endpoints
- Retry on 401 authentication errors
- Camera listing and management
- RTSP stream start/stop (local and cloud)
- Station/hub listing
- Event history for camera thumbnails

## Important Notes

- An email/password combo cannot work with both the Eufy Security mobile app and this library simultaneously. It is recommended to create a secondary "guest" account with a separate email address.
- Eufy may require CAPTCHA verification for new logins. Handle `CaptchaRequiredError` to prompt users for CAPTCHA solutions.

## License

MIT License
