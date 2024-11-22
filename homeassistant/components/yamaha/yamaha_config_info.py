"""Configuration Information for Yamaha."""

from aiohttp import ClientSession
import defusedxml.ElementTree as ET

ns = {"s": "urn:schemas-upnp-org:device-1-0"}


class YamahaConfigInfo:
    """Configuration Info for Yamaha Receivers."""

    def __init__(
            self, host: str
    ) -> None:
        """Initialize the Configuration Info for Yamaha Receiver."""
        self.ctrl_url: str | None = f"http://{host}:80/YamahaRemoteControl/ctrl"

    @classmethod
    async def check_yamaha_ssdp(cls, location: str, client: ClientSession):
        """Check if the Yamaha receiver has a valid control URL."""
        res = await client.get(location)
        text = await res.text()
        return text.find('<yamaha:X_controlURL>/YamahaRemoteControl/ctrl</yamaha:X_controlURL>') != -1

    @classmethod
    async def get_upnp_serial_and_model(cls, host : str, client: ClientSession):
        """Retrieve the serial_number and model from the SSDP description URL."""
        res = await client.get(f"http://{host}:49154/MediaRenderer/desc.xml" )
        root = ET.fromstring(await res.text())
        serial_number = root.find("./s:device/s:serialNumber", ns).text
        model_name = root.find("./s:device/s:modelName", ns).text
        return serial_number, model_name
