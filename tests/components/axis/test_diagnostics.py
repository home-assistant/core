"""Test Axis diagnostics."""
import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from .const import API_DISCOVERY_BASIC_DEVICE_INFO

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_BASIC_DEVICE_INFO])
async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, setup_config_entry
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, setup_config_entry
    ) == {
        "config": {
            "entry_id": setup_config_entry.entry_id,
            "version": 3,
            "domain": "axis",
            "title": "Mock Title",
            "data": {
                "host": "1.2.3.4",
                "username": REDACTED,
                "password": REDACTED,
                "port": 80,
                "model": "model",
                "name": "name",
            },
            "options": {"events": True},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "camera_sources": {
            "Image": "http://1.2.3.4:80/axis-cgi/jpg/image.cgi",
            "MJPEG": "http://1.2.3.4:80/axis-cgi/mjpg/video.cgi",
            "Stream": "rtsp://user:pass@1.2.3.4/axis-media/media.amp?videocodec=h264",
        },
        "api_discovery": [
            {
                "id": "api-discovery",
                "name": "API Discovery Service",
                "version": "1.0",
            },
            {
                "id": "param-cgi",
                "name": "Legacy Parameter Handling",
                "version": "1.0",
            },
            {
                "id": "basic-device-info",
                "name": "Basic Device Information",
                "version": "1.1",
            },
        ],
        "basic_device_info": {
            "ProdNbr": "M1065-LW",
            "ProdType": "Network Camera",
            "SerialNumber": REDACTED,
            "Version": "9.80.1",
        },
        "params": {
            "root.IOPort": {
                "I0.Configurable": "no",
                "I0.Direction": "input",
                "I0.Input.Name": "PIR sensor",
                "I0.Input.Trig": "closed",
            },
            "root.Input": {"NbrOfInputs": "1"},
            "root.Output": {"NbrOfOutputs": "0"},
            "root.Properties": {
                "API.HTTP.Version": "3",
                "API.Metadata.Metadata": "yes",
                "API.Metadata.Version": "1.0",
                "EmbeddedDevelopment.Version": "2.16",
                "Firmware.BuildDate": "Feb 15 2019 09:42",
                "Firmware.BuildNumber": "26",
                "Firmware.Version": "9.10.1",
                "Image.Format": "jpeg,mjpeg,h264",
                "Image.NbrOfViews": "2",
                "Image.Resolution": "1920x1080,1280x960,1280x720,1024x768,1024x576,800x600,640x480,640x360,352x240,320x240",
                "Image.Rotation": "0,180",
                "System.SerialNumber": REDACTED,
            },
            "root.StreamProfile": {
                "MaxGroups": "26",
                "S0.Description": "profile_1_description",
                "S0.Name": "profile_1",
                "S0.Parameters": "videocodec=h264",
                "S1.Description": "profile_2_description",
                "S1.Name": "profile_2",
                "S1.Parameters": "videocodec=h265",
            },
        },
    }
