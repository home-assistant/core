import logging
from aiohttp import ClientSession, ClientResponseError

_LOGGER = logging.getLogger(__name__)


class TuneBladeApiClient:
    def __init__(self, host: str, port: int, session: ClientSession):
        self._base_url = f"http://{host}:{port}/v2"
        self._session = session

    def _get_auth(self):
        return None  # Add auth if needed

    async def async_get_data(self):
        """Fetch all devices (including master) with connection and volume status."""
        try:
            async with self._session.get(self._base_url, auth=self._get_auth()) as resp:
                resp.raise_for_status()
                raw_text = await resp.text()

            _LOGGER.debug("Raw TuneBlade response: %s", repr(raw_text))

            devices = {}
            for line in raw_text.strip().splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue

                device_id = parts[0]
                connected_flag = parts[1]
                volume_str = parts[2]
                name = " ".join(parts[3:]) if len(parts) > 3 else device_id

                try:
                    connected = int(connected_flag) != 0
                except ValueError:
                    connected = False

                try:
                    volume = int(volume_str)
                except ValueError:
                    volume = None

                devices[device_id] = {
                    "id": device_id,
                    "name": name.strip(),
                    "connected": connected,
                    "volume": volume,
                    "status_code": connected_flag,
                }

            return devices

        except Exception as err:
            _LOGGER.error("Failed to fetch TuneBlade device data: %s", err)
            return {}

    async def connect(self, device_id: str):
        url = f"{self._base_url}/{device_id}/Status/Connect"
        await self._send_command(url, f"connect {device_id}")

    async def disconnect(self, device_id: str):
        url = f"{self._base_url}/{device_id}/Status/Disconnect"
        await self._send_command(url, f"disconnect {device_id}")

    async def set_volume(self, device_id: str, volume: int):
        url = f"{self._base_url}/{device_id}/Volume/{volume}"
        await self._send_command(url, f"set volume {volume} for {device_id}")

    async def _send_command(self, url: str, description: str):
        try:
            async with self._session.get(url, auth=self._get_auth()) as resp:
                resp.raise_for_status()
            _LOGGER.debug("Command succeeded: %s", description)
        except ClientResponseError as err:
            _LOGGER.error("HTTP error during %s: %s", description, err)
        except Exception as err:
            _LOGGER.error("Error during %s: %s", description, err)
