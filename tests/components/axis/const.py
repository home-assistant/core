"""Constants for Axis integration tests."""


MAC = "00408C123456"
FORMATTED_MAC = "00:40:8c:12:34:56"
MODEL = "model"
NAME = "name"

DEFAULT_HOST = "1.2.3.4"


API_DISCOVERY_RESPONSE = {
    "method": "getApiList",
    "apiVersion": "1.0",
    "data": {
        "apiList": [
            {"id": "api-discovery", "version": "1.0", "name": "API Discovery Service"},
            {"id": "param-cgi", "version": "1.0", "name": "Legacy Parameter Handling"},
        ]
    },
}

API_DISCOVERY_BASIC_DEVICE_INFO = {
    "id": "basic-device-info",
    "version": "1.1",
    "name": "Basic Device Information",
}
API_DISCOVERY_MQTT = {"id": "mqtt-client", "version": "1.0", "name": "MQTT Client API"}
API_DISCOVERY_PORT_MANAGEMENT = {
    "id": "io-port-management",
    "version": "1.0",
    "name": "IO Port Management",
}

APPLICATIONS_LIST_RESPONSE = """<reply result="ok">
 <application Name="vmd" NiceName="AXIS Video Motion Detection" Vendor="Axis Communications" Version="4.2-0" ApplicationID="143440" License="None" Status="Running" ConfigurationPage="local/vmd/config.html" VendorHomePage="http://www.axis.com" />
</reply>"""

BASIC_DEVICE_INFO_RESPONSE = {
    "apiVersion": "1.1",
    "data": {
        "propertyList": {
            "ProdNbr": "M1065-LW",
            "ProdType": "Network Camera",
            "SerialNumber": MAC,
            "Version": "9.80.1",
        }
    },
}


MQTT_CLIENT_RESPONSE = {
    "apiVersion": "1.0",
    "context": "some context",
    "method": "getClientStatus",
    "data": {"status": {"state": "active", "connectionStatus": "Connected"}},
}

PORT_MANAGEMENT_RESPONSE = {
    "apiVersion": "1.0",
    "method": "getPorts",
    "data": {
        "numberOfPorts": 1,
        "items": [
            {
                "port": "0",
                "configurable": False,
                "usage": "",
                "name": "PIR sensor",
                "direction": "input",
                "state": "open",
                "normalState": "open",
            }
        ],
    },
}

VMD4_RESPONSE = {
    "apiVersion": "1.4",
    "method": "getConfiguration",
    "context": "Axis library",
    "data": {
        "cameras": [{"id": 1, "rotation": 0, "active": True}],
        "profiles": [
            {"filters": [], "camera": 1, "triggers": [], "name": "Profile 1", "uid": 1}
        ],
    },
}

BRAND_RESPONSE = """root.Brand.Brand=AXIS
root.Brand.ProdFullName=AXIS M1065-LW Network Camera
root.Brand.ProdNbr=M1065-LW
root.Brand.ProdShortName=AXIS M1065-LW
root.Brand.ProdType=Network Camera
root.Brand.ProdVariant=
root.Brand.WebURL=http://www.axis.com
"""

IMAGE_RESPONSE = """root.Image.I0.Enabled=yes
root.Image.I0.Name=View Area 1
root.Image.I0.Source=0
root.Image.I1.Enabled=no
root.Image.I1.Name=View Area 2
root.Image.I1.Source=0
"""

PORTS_RESPONSE = """root.Input.NbrOfInputs=1
root.IOPort.I0.Configurable=no
root.IOPort.I0.Direction=input
root.IOPort.I0.Input.Name=PIR sensor
root.IOPort.I0.Input.Trig=closed
root.Output.NbrOfOutputs=0
"""

PROPERTIES_RESPONSE = f"""root.Properties.API.HTTP.Version=3
root.Properties.API.Metadata.Metadata=yes
root.Properties.API.Metadata.Version=1.0
root.Properties.EmbeddedDevelopment.Version=2.16
root.Properties.Firmware.BuildDate=Feb 15 2019 09:42
root.Properties.Firmware.BuildNumber=26
root.Properties.Firmware.Version=9.10.1
root.Properties.Image.Format=jpeg,mjpeg,h264
root.Properties.Image.NbrOfViews=2
root.Properties.Image.Resolution=1920x1080,1280x960,1280x720,1024x768,1024x576,800x600,640x480,640x360,352x240,320x240
root.Properties.Image.Rotation=0,180
root.Properties.System.SerialNumber={MAC}
"""

PTZ_RESPONSE = ""


STREAM_PROFILES_RESPONSE = """root.StreamProfile.MaxGroups=26
root.StreamProfile.S0.Description=profile_1_description
root.StreamProfile.S0.Name=profile_1
root.StreamProfile.S0.Parameters=videocodec=h264
root.StreamProfile.S1.Description=profile_2_description
root.StreamProfile.S1.Name=profile_2
root.StreamProfile.S1.Parameters=videocodec=h265
"""

VIEW_AREAS_RESPONSE = {"apiVersion": "1.0", "method": "list", "data": {"viewAreas": []}}
