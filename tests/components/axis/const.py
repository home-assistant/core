"""Constants for Axis integration tests."""

from axis.models.api import CONTEXT

MAC = "00408C123456"
FORMATTED_MAC = "00:40:8c:12:34:56"
MODEL = "A1234"
NAME = "home"

DEFAULT_HOST = "1.2.3.4"


API_DISCOVERY_RESPONSE = {
    "method": "getApiList",
    "apiVersion": "1.0",
    "context": CONTEXT,
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
 <application Name="fenceguard" NiceName="AXIS Fence Guard" Vendor="Axis Communications" Version="2.2-6" ApplicationID="47775" License="None" Status="Running" ConfigurationPage="local/fenceguard/config.html" VendorHomePage="http://www.axis.com" LicenseName="Proprietary" />
 <application Name="loiteringguard" NiceName="AXIS Loitering Guard" Vendor="Axis Communications" Version="2.2-6" ApplicationID="46775" License="None" Status="Running" ConfigurationPage="local/loiteringguard/config.html" VendorHomePage="http://www.axis.com" LicenseName="Proprietary" />
 <application Name="motionguard" NiceName="AXIS Motion Guard" Vendor="Axis Communications" Version="2.2-6" ApplicationID="48170" License="None" Status="Running" ConfigurationPage="local/motionguard/config.html" VendorHomePage="http://www.axis.com" LicenseName="Proprietary" />
 <application Name="vmd" NiceName="AXIS Video Motion Detection" Vendor="Axis Communications" Version="4.2-0" ApplicationID="143440" License="None" Status="Running" ConfigurationPage="local/vmd/config.html" VendorHomePage="http://www.axis.com" />
 <application Name="objectanalytics" NiceName="AXIS Object Analytics" Vendor="Axis Communications" Version="1.0-0" ApplicationID="143440" License="None" Status="Running" ConfigurationPage="local/vmd/config.html" VendorHomePage="http://www.axis.com" />
</reply>"""

BASIC_DEVICE_INFO_RESPONSE = {
    "apiVersion": "1.1",
    "context": CONTEXT,
    "data": {
        "propertyList": {
            "ProdNbr": "M1065-LW",
            "ProdType": "Network Camera",
            "SerialNumber": MAC,
            "Version": "9.80.1",
            "Architecture": "str",
            "Brand": "str",
            "BuildDate": "str",
            "HardwareID": "str",
            "ProdFullName": "str",
            "ProdShortName": "str",
            "ProdVariant": "str",
            "Soc": "str",
            "SocSerialNumber": "str",
            "WebURL": "str",
        }
    },
}


MQTT_CLIENT_RESPONSE = {
    "method": "getClientStatus",
    "apiVersion": "1.0",
    "context": CONTEXT,
    "data": {
        "status": {"state": "active", "connectionStatus": "Connected"},
        "config": {
            "server": {"protocol": "tcp", "host": "192.168.0.90", "port": 1883},
            "deviceTopicPrefix": f"axis/{MAC}",
        },
    },
}


PORT_MANAGEMENT_RESPONSE = {
    "apiVersion": "1.0",
    "method": "getPorts",
    "context": CONTEXT,
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

APP_VMD4_RESPONSE = {
    "apiVersion": "1.4",
    "method": "getConfiguration",
    "context": CONTEXT,
    "data": {
        "cameras": [{"id": 1, "rotation": 0, "active": True}],
        "profiles": [
            {"filters": [], "camera": 1, "triggers": [], "name": "Profile 1", "uid": 1}
        ],
        "configurationStatus": 2,
    },
}

APP_AOA_RESPONSE = {
    "apiVersion": "1.0",
    "context": "Axis library",
    "data": {
        "devices": [{"id": 1, "rotation": 180, "type": "camera"}],
        "metadataOverlay": [],
        "perspectives": [],
        "scenarios": [
            {
                "devices": [{"id": 1}],
                "filters": [
                    {"distance": 5, "type": "distanceSwayingObject"},
                    {"time": 1, "type": "timeShortLivedLimit"},
                    {"height": 3, "type": "sizePercentage", "width": 3},
                ],
                "id": 1,
                "name": "Scenario 1",
                "objectClassifications": [],
                "perspectives": [],
                "presets": [],
                "triggers": [
                    {
                        "type": "includeArea",
                        "vertices": [
                            [-0.97, -0.97],
                            [-0.97, 0.97],
                            [0.97, 0.97],
                            [0.97, -0.97],
                        ],
                    }
                ],
                "type": "motion",
            },
        ],
        "status": {},
    },
    "method": "getConfiguration",
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
root.Image.I0.Appearance.ColorEnabled=yes
root.Image.I0.Appearance.Compression=30
root.Image.I0.Appearance.MirrorEnabled=no
root.Image.I0.Appearance.Resolution=1920x1080
root.Image.I0.Appearance.Rotation=0
root.Image.I0.MPEG.Complexity=50
root.Image.I0.MPEG.ConfigHeaderInterval=1
root.Image.I0.MPEG.FrameSkipMode=drop
root.Image.I0.MPEG.ICount=1
root.Image.I0.MPEG.PCount=31
root.Image.I0.MPEG.UserDataEnabled=no
root.Image.I0.MPEG.UserDataInterval=1
root.Image.I0.MPEG.ZChromaQPMode=off
root.Image.I0.MPEG.ZFpsMode=fixed
root.Image.I0.MPEG.ZGopMode=fixed
root.Image.I0.MPEG.ZMaxGopLength=300
root.Image.I0.MPEG.ZMinFps=0
root.Image.I0.MPEG.ZStrength=10
root.Image.I0.MPEG.H264.Profile=high
root.Image.I0.MPEG.H264.PSEnabled=no
root.Image.I0.Overlay.Enabled=no
root.Image.I0.Overlay.XPos=0
root.Image.I0.Overlay.YPos=0
root.Image.I0.Overlay.MaskWindows.Color=black
root.Image.I0.RateControl.MaxBitrate=0
root.Image.I0.RateControl.Mode=vbr
root.Image.I0.RateControl.Priority=framerate
root.Image.I0.RateControl.TargetBitrate=0
root.Image.I0.SizeControl.MaxFrameSize=0
root.Image.I0.Stream.Duration=0
root.Image.I0.Stream.FPS=0
root.Image.I0.Stream.NbrOfFrames=0
root.Image.I0.Text.BGColor=black
root.Image.I0.Text.ClockEnabled=no
root.Image.I0.Text.Color=white
root.Image.I0.Text.DateEnabled=no
root.Image.I0.Text.Position=top
root.Image.I0.Text.String=
root.Image.I0.Text.TextEnabled=no
root.Image.I0.Text.TextSize=medium
root.Image.I0.TriggerData.AudioEnabled=yes
root.Image.I0.TriggerData.MotionDetectionEnabled=yes
root.Image.I0.TriggerData.MotionLevelEnabled=no
root.Image.I0.TriggerData.TamperingEnabled=yes
root.Image.I0.TriggerData.UserTriggers=
root.Image.I1.Appearance.ColorEnabled=yes
root.Image.I1.Appearance.Compression=30
root.Image.I1.Appearance.MirrorEnabled=no
root.Image.I1.Appearance.Resolution=1920x1080
root.Image.I1.Appearance.Rotation=0
root.Image.I1.MPEG.Complexity=50
root.Image.I1.MPEG.ConfigHeaderInterval=1
root.Image.I1.MPEG.FrameSkipMode=drop
root.Image.I1.MPEG.ICount=1
root.Image.I1.MPEG.PCount=31
root.Image.I1.MPEG.UserDataEnabled=no
root.Image.I1.MPEG.UserDataInterval=1
root.Image.I1.MPEG.ZChromaQPMode=off
root.Image.I1.MPEG.ZFpsMode=fixed
root.Image.I1.MPEG.ZGopMode=fixed
root.Image.I1.MPEG.ZMaxGopLength=300
root.Image.I1.MPEG.ZMinFps=0
root.Image.I1.MPEG.ZStrength=10
root.Image.I1.MPEG.H264.Profile=high
root.Image.I1.MPEG.H264.PSEnabled=no
root.Image.I1.Overlay.Enabled=no
root.Image.I1.Overlay.XPos=0
root.Image.I1.Overlay.YPos=0
root.Image.I1.RateControl.MaxBitrate=0
root.Image.I1.RateControl.Mode=vbr
root.Image.I1.RateControl.Priority=framerate
root.Image.I1.RateControl.TargetBitrate=0
root.Image.I1.SizeControl.MaxFrameSize=0
root.Image.I1.Stream.Duration=0
root.Image.I1.Stream.FPS=0
root.Image.I1.Stream.NbrOfFrames=0
root.Image.I1.Text.BGColor=black
root.Image.I1.Text.ClockEnabled=no
root.Image.I1.Text.Color=white
root.Image.I1.Text.DateEnabled=no
root.Image.I1.Text.Position=top
root.Image.I1.Text.String=
root.Image.I1.Text.TextEnabled=no
root.Image.I1.Text.TextSize=medium
root.Image.I1.TriggerData.AudioEnabled=yes
root.Image.I1.TriggerData.MotionDetectionEnabled=yes
root.Image.I1.TriggerData.MotionLevelEnabled=no
root.Image.I1.TriggerData.TamperingEnabled=yes
root.Image.I1.TriggerData.UserTriggers=
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
