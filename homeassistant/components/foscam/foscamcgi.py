"""A module to exploit Foscam Foscam FI9821W/P/HD816W/P camera.

2016-01-22 Python 3 update by https://github.com/markomanninen
"""

# Python 3 support. Also print -> print().

from threading import Thread
from urllib.parse import unquote, urlencode
from urllib.request import urlopen

try:
    import ssl

    ssl_enabled = True
except ImportError:
    ssl_enabled = False

from collections import OrderedDict
import logging
from xml.etree.ElementTree import ParseError

from defusedxml.ElementTree import fromstring as defused_fromstring

_LOGGER = logging.getLogger(__name__)
# Foscam error code.
FOSCAM_SUCCESS = 0
ERROR_FOSCAM_FORMAT = -1
ERROR_FOSCAM_AUTH = -2
ERROR_FOSCAM_CMD = -3  # Access deny. May the cmd is not supported.
ERROR_FOSCAM_EXE = -4  # CGI execute fail.
ERROR_FOSCAM_TIMEOUT = -5
ERROR_FOSCAM_UNKNOWN = -7  # -6 and -8 are reserved.
ERROR_FOSCAM_UNAVAILABLE = -8  # Disconnected or not a cam.


class FoscamError(Exception):
    """Custom exception class for Foscam-related errors."""

    def __init__(self, code):
        """Initialize the FoscamError instance."""
        super().__init__()
        self.code = int(code)

    def __str__(self):
        """Return a string representation of the error."""
        return f"ErrorCode: {self.code}"


class FoscamCamera:
    """A python implementation of the foscam HD816W."""

    def __init__(self, host, port, usr, pwd, daemon=False, ssl_=None, verbose=True):
        """If ``daemon`` is True, the command will be sent unblockedly."""
        self.host = host
        self.port = port
        self.usr = usr
        self.pwd = pwd
        self.daemon = daemon
        self.verbose = verbose
        self.ssl = ssl_
        if ssl_enabled:
            if port == 443 and ssl is None:
                self.ssl = True
        if self.ssl is None:
            self.ssl = False

    @property
    def url(self) -> str:
        """Return now url and port."""
        return f"{self.host}:{self.port}"

    def send_command(self, cmd, params=None, raw=False):
        """Send command to foscam."""
        paramstr = ""
        if params:
            paramstr = urlencode(params)
            paramstr = "&" + paramstr if paramstr else ""
        cmdurl = f"http://{self.url}/cgi-bin/CGIProxy.fcgi?usr={self.usr}&pwd={self.pwd}&cmd={cmd}{paramstr}"
        if self.ssl and ssl_enabled:
            cmdurl = cmdurl.replace("http:", "https:")

        # Parse parameters from response string.
        if self.verbose:
            _LOGGER.debug("Send Foscam command: %s", cmdurl)
        try:
            raw_string = ""
            if self.ssl and ssl_enabled:
                gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)  # disable cert
                with urlopen(cmdurl, context=gcontext, timeout=5) as response:
                    raw_string = response.read()
            else:
                with urlopen(cmdurl, timeout=5) as response:
                    raw_string = response.read()
            if raw:
                if self.verbose:
                    _LOGGER.debug(
                        "Returning raw Foscam response: len=%d", len(raw_string)
                    )
                return FOSCAM_SUCCESS, raw_string
            root = defused_fromstring(raw_string)
        except ParseError as e:
            if self.verbose:
                _LOGGER.debug("Foscam exception:%s", e)
            return ERROR_FOSCAM_UNAVAILABLE, None
        code = ERROR_FOSCAM_UNKNOWN
        params = OrderedDict()
        for child in root.iter():
            if child.tag == "result":
                code = int(child.text)

            elif child.tag != "CGI_Result":
                params[child.tag] = (
                    unquote(child.text) if child.text is not None else None
                )

        if self.verbose:
            _LOGGER.debug("Received Foscam response: %s, %s", code, params)
        return code, params

    def execute_command(self, cmd, params=None, callback=None, raw=False):
        """Execute a command and return a parsed response."""

        def execute_with_callbacks(cmd, params=None, callback=None, raw=False):
            code, params = self.send_command(cmd, params, raw)
            if callback:
                callback(code, params)
            return code, params

        if self.daemon:
            t = Thread(
                target=execute_with_callbacks,
                args=(cmd,),
                kwargs={"params": params, "callback": callback, "raw": raw},
            )
            t.daemon = True
            t.start()
            return None
        return execute_with_callbacks(cmd, params, callback, raw)

    # *************** Network ******************

    def get_ip_info(self, callback=None):
        """Get ip information."""
        return self.execute_command("getIPInfo", callback=callback)

    def set_ip_info(
        self, is_dhcp, ip="", gate="", mask="", dns1="", dns2="", callback=None
    ):
        """isDHCP: 0(False), 1(True)System will reboot automatically to take effect after call this CGI command."""
        params = {
            "isDHCP": is_dhcp,
            "ip": ip,
            "gate": gate,
            "mask": mask,
            "dns1": dns1,
            "dns2": dns2,
        }

        return self.execute_command("setIpInfo", params, callback=callback)

    def get_port_info(self, callback=None):
        """Get http port and media port of camera."""
        return self.execute_command("getPortInfo", callback=callback)

    def set_port_info(self, webport, mediaport, httpsport, onvifport, callback=None):
        """Set http port and media port of camera."""
        params = {
            "webPort": webport,
            "mediaPort": mediaport,
            "httpsPort": httpsport,
            "onvifPort": onvifport,
        }
        return self.execute_command("setPortInfo", params, callback=callback)

    def refresh_wifi_list(self, callback=None):
        """Start scan the aps around.This operation may takes a while, about 20s or above,the other operation on this device will be blocked during the period."""
        return self.execute_command("refreshWifiList", callback=callback)

    def get_wifi_list(self, startno, callback=None):
        """Get the aps around after refreshWifiList.Note: Only 10 aps will be returned one time."""
        params = {"startNo": startno}
        return self.execute_command("getWifiList", params, callback=callback)

    def set_wifi_setting(
        self,
        ssid,
        psk,
        isenable,
        isusewifi,
        nettype,
        encryptype,
        authmode,
        keyformat,
        defaultkey,
        key1="",
        key2="",
        key3="",
        key4="",
        key1len=64,
        key2len=64,
        key3len=64,
        key4len=64,
        callback=None,
    ):
        """Set wifi config.Camera will not connect to AP unless you enject your cable."""
        params = {
            "isEnable": isenable,
            "isUseWifi": isusewifi,
            "ssid": ssid,
            "netType": nettype,
            "encryptType": encryptype,
            "psk": psk,
            "authMode": authmode,
            "keyFormat": keyformat,
            "defaultKey": defaultkey,
            "key1": key1,
            "key2": key2,
            "key3": key3,
            "key4": key4,
            "key1Len": key1len,
            "key2Len": key2len,
            "key3Len": key3len,
            "key4Len": key4len,
        }
        return self.execute_command("setWifiSetting", params, callback=callback)

    def get_wifi_config(self, callback=None):
        """Get wifi config."""
        return self.execute_command("getWifiConfig", callback=callback)

    def get_upnp_config(self, callback=None):
        """Get UpnP config."""
        return self.execute_command("getUPnPConfig", callback=callback)

    def set_upnp_config(self, isenable, callback=None):
        """Set UPnP config."""
        params = {"isEnable": isenable}
        return self.execute_command("setUPnPConfig", params, callback=callback)

    def get_ddns_config(self, callback=None):
        """Get DDNS config."""
        return self.execute_command("getDDNSConfig", callback=callback)

    def set_ddns_config(
        self, isenable, hostname, ddnsserver, user, password, callback=None
    ):
        """Set DDNS config."""
        params = {
            "isEnable": isenable,
            "hostName": hostname,
            "ddnsServer": ddnsserver,
            "user": user,
            "password": password,
        }
        return self.execute_command("setDDNSConfig", params, callback=callback)

    # *************** AV Settings  ******************

    def get_sub_video_stream_type(self, callback=None):
        """Get the stream type of sub stream."""
        return self.execute_command("getSubVideoStreamType", callback=callback)

    def set_sub_video_stream_type(self, format, callback=None):
        """Set the stream format of sub stream.Supported format: (1) H264 : 0(2) MotionJpeg."""
        params = {"format": format}
        return self.execute_command("setSubVideoStreamType", params, callback=callback)

    def set_sub_stream_format(self, format, callback=None):
        """Set the stream format of sub stream????."""
        params = {"format": format}
        return self.execute_command("setSubStreamFormat", params, callback=callback)

    def get_main_video_stream_type(self, callback=None):
        """Get the stream type of main stream."""
        return self.execute_command("getMainVideoStreamType", callback=callback)

    def set_main_video_stream_type(self, streamtype, callback=None):
        """Set the stream type of main stream."""
        params = {"streamType": streamtype}
        return self.execute_command("setMainVideoStreamType", params, callback=callback)

    def get_video_stream_param(self, callback=None):
        """Get video stream param."""
        return self.execute_command("getVideoStreamParam", callback=callback)

    def set_video_stream_param(
        self, streamtype, resolution, bitrate, framerate, gop, isvbr, callback=None
    ):
        """Set the video stream param of stream N."""
        params = {
            "streamType": streamtype,
            "resolution": resolution,
            "bitRate": bitrate,
            "frameRate": framerate,
            "GOP": gop,
            "isVBR": isvbr,
        }
        return self.execute_command("setVideoStreamParam", params, callback=callback)

    def mirror_video(self, is_mirror, callback=None):
        """Mirror video``is_mirror``: 0 not mirror, 1 mirror."""
        params = {"isMirror": is_mirror}
        return self.execute_command("mirrorVideo", params, callback=callback)

    def flip_video(self, is_flip, callback=None):
        """Flip video``is_flip``: 0 Not flip, 1 Flip."""
        params = {"isFlip": is_flip}
        return self.execute_command("flipVideo", params, callback=callback)

    def get_mirror_and_flip_setting(self, callback=None):
        """Get Flip and miirror setting."""
        return self.execute_command("getMirrorAndFlipSetting", None, callback=callback)

    # *************** User account ******************

    def change_user_name(self, usrname, newusrname, callback=None):
        """Change user name."""
        params = {
            "usrName": usrname,
            "newUsrName": newusrname,
        }
        return self.execute_command("changeUserName", params, callback=callback)

    def change_password(self, usrname, oldpwd, newpwd, callback=None):
        """Change password."""
        params = {
            "usrName": usrname,
            "oldPwd": oldpwd,
            "newPwd": newpwd,
        }
        return self.execute_command("changePassword", params, callback=callback)

    # *************** Device manage *******************

    def set_system_time(
        self,
        time_source,
        ntp_server,
        date_format,
        time_format,
        time_zone,
        is_dst,
        dst,
        year,
        mon,
        day,
        hour,
        minute,
        sec,
        callback=None,
    ):
        """Set system time."""
        if ntp_server not in [
            "time.nist.gov",
            "time.kriss.re.kr",
            "time.windows.com",
            "time.nuri.net",
            "Auto",
        ]:
            raise ValueError("Unsupported ntpServer")

        params = {
            "timeSource": time_source,
            "ntpServer": ntp_server,
            "dateFormat": date_format,
            "timeFormat": time_format,
            "timeZone": time_zone,
            "isDst": is_dst,
            "dst": dst,
            "year": year,
            "mon": mon,
            "day": day,
            "hour": hour,
            "minute": minute,
            "sec": sec,
        }

        return self.execute_command("setSystemTime", params, callback=callback)

    def get_system_time(self, callback=None):
        """Get system time."""
        return self.execute_command("getSystemTime", callback=callback)

    def get_dev_name(self, callback=None):
        """Get camera name."""
        return self.execute_command("getDevName", callback=callback)

    def set_dev_name(self, devname, callback=None):
        """Set camera name."""
        params = {"devName": devname.encode("gbk")}
        return self.execute_command("setDevName", params, callback=callback)

    def get_dev_state(self, callback=None):
        """Get all device state."""
        return self.execute_command("getDevState", callback=callback)

    def get_dev_info(self, callback=None):
        """Get camera informationcmd: getDevInfo."""
        return self.execute_command("getDevInfo", callback=callback)

    def open_infra_led(self, callback=None):
        """Force open infra ledcmd: openInfraLed."""
        return self.execute_command("openInfraLed", {}, callback=callback)

    def close_infra_led(self, callback=None):
        """Force close infra ledcmd: closeInfraLed."""
        return self.execute_command("closeInfraLed", callback=callback)

    def get_infra_led_config(self, callback=None):
        """Get Infrared LED configurationcmd: getInfraLedConfig."""
        return self.execute_command("getInfraLedConfig", callback=callback)

    def set_infra_led_config(self, mode, callback=None):
        """Set Infrared LED configurationcmd: setInfraLedConfigmode(0,1): 0=Auto mode, 1=Manual mode."""
        params = {"mode": mode}
        return self.execute_command("setInfraLedConfig", params, callback=callback)

    def get_product_all_info(self, callback=None):
        """Get camera informationcmd: getProductAllInfo."""
        return self.execute_command("getProductAllInfo", callback=callback)

    # *************** PTZ Control *******************

    def ptz_move_up(self, callback=None):
        """Move up."""
        return self.execute_command("ptzMoveUp", callback=callback)

    def ptz_move_down(self, callback=None):
        """Move down."""
        return self.execute_command("ptzMoveDown", callback=callback)

    def ptz_move_left(self, callback=None):
        """Move left."""
        return self.execute_command("ptzMoveLeft", callback=callback)

    def ptz_move_right(self, callback=None):
        """Move right."""
        return self.execute_command("ptzMoveRight", callback=callback)

    def ptz_move_top_left(self, callback=None):
        """Move to top left."""
        return self.execute_command("ptzMoveTopLeft", callback=callback)

    def ptz_move_top_right(self, callback=None):
        """Move to top right."""
        return self.execute_command("ptzMoveTopRight", callback=callback)

    def ptz_move_bottom_left(self, callback=None):
        """Move to bottom left."""
        return self.execute_command("ptzMoveBottomLeft", callback=callback)

    def ptz_move_bottom_right(self, callback=None):
        """Move to bottom right."""
        return self.execute_command("ptzMoveBottomRight", callback=callback)

    def ptz_stop_run(self, callback=None):
        """Stop run PT."""
        return self.execute_command("ptzStopRun", callback=callback)

    def ptz_reset(self, callback=None):
        """Reset PT to default position."""
        return self.execute_command("ptzReset", callback=callback)

    def ptz_get_preset(self, callback=None):
        """Get presets."""
        return self.execute_command("getPTZPresetPointList", callback=callback)

    def ptz_goto_preset(self, name, callback=None):
        """Move to preset."""
        params = {"name": name}
        return self.execute_command("ptzGotoPresetPoint", params, callback=callback)

    def get_ptz_speed(self, callback=None):
        """Get the speed of PT."""
        return self.execute_command("getPTZSpeed", callback=callback)

    def set_ptz_speed(self, speed, callback=None):
        """Set the speed of PT."""
        return self.execute_command("setPTZSpeed", {"speed": speed}, callback=callback)

    def get_ptz_selftestmode(self, callback=None):
        """Get the selftest mode of PTZ."""
        return self.execute_command("getPTZSelfTestMode", callback=callback)

    def set_ptz_selftestmode(self, mode=0, callback=None):
        """Set the selftest mode of PTZ."""
        return self.execute_command(
            "setPTZSelfTestMode", {"mode": mode}, callback=callback
        )

    def get_ptz_preset_point_list(self, callback=None):
        """Get the preset list."""
        return self.execute_command("getPTZPresetPointList", {}, callback=callback)

    def ptz_zoom_in(self, callback=None):
        """Get the preset list.Zoom In."""
        return self.execute_command("zoomIn", callback=callback)

    def ptz_zoom_out(self, callback=None):
        """Move to bottom right."""
        return self.execute_command("zoomOut", callback=callback)

    def ptz_zoom_stop(self, callback=None):
        """Stop run PT."""
        return self.execute_command("zoomStop", callback=callback)

    def sleep(self, callback=None):
        """Rotate to sleep position and sleep."""
        return self.execute_command("alexaSleep", callback=callback)

    def wake_up(self, callback=None):
        """Wakeup camera."""
        return self.execute_command("alexaWakeUp", callback=callback)

    def is_asleep(self, callback=None):
        """Wakeup camera."""
        ret, data = self.execute_command("getAlexaState", callback=callback)

        is_asleep = int(data["state"]) == 1 if ret == 0 else False

        return ret, is_asleep

    # *************** AV Function *******************
    def get_motion_detect_config(self, callback=None):
        """Get motion detect config."""
        return self.execute_command("getMotionDetectConfig", callback=callback)

    def set_motion_detect_config(self, params, callback=None):
        """Get motion detect config."""
        return self.execute_command("setMotionDetectConfig", params, callback=callback)

    def set_motion_detection(self, enabled=1):
        """Get the current config and set the motion detection on or off."""
        result, current_config = self.get_motion_detect_config()
        if result != FOSCAM_SUCCESS:
            return result
        current_config["isEnable"] = enabled
        self.set_motion_detect_config(current_config)
        return FOSCAM_SUCCESS

    def enable_motion_detection(self):
        """Enable motion detection."""
        return self.set_motion_detection(1)

    def disable_motion_detection(self):
        """Disable motion detection."""
        return self.set_motion_detection(0)

    # These API calls support FI9900P devices, which use a different CGI command
    def get_motion_detect_config1(self, callback=None):
        """Get motion detect config."""
        return self.execute_command("getMotionDetectConfig1", callback=callback)

    def set_motion_detect_config1(self, params, callback=None):
        """Get motion detect config."""
        return self.execute_command("setMotionDetectConfig1", params, callback=callback)

    def set_motion_detection1(self, enabled=1):
        """Get the current config and set the motion detection on or off."""
        result, current_config = self.get_motion_detect_config1()
        if result != FOSCAM_SUCCESS:
            return result
        current_config["isEnable"] = enabled
        self.set_motion_detect_config1(current_config)
        return None

    def enable_motion_detection1(self):
        """Enable motion detection."""
        self.set_motion_detection1(1)

    def disable_motion_detection1(self):
        """Disable motion detection."""
        self.set_motion_detection1(0)

    def get_alarm_record_config(self, callback=None):
        """Get alarm record config."""
        return self.execute_command("getAlarmRecordConfig", callback=callback)

    def set_alarm_record_config(
        self,
        is_enable_prerecord=1,
        prerecord_secs=5,
        alarm_record_secs=300,
        callback=None,
    ):
        """Set alarm record configReturn: set result(0-success, -1-error)."""
        params = {
            "isEnablePreRecord": is_enable_prerecord,
            "preRecordSecs": prerecord_secs,
            "alarmRecordSecs": alarm_record_secs,
        }
        return self.execute_command("setAlarmRecordConfig", params, callback=callback)

    def get_local_alarm_record_config(self, callback=None):
        """Get local alarm-record config."""
        return self.execute_command("getLocalAlarmRecordConfig", callback=callback)

    def set_local_alarm_record_config(
        self, is_enable_local_alarm_record=1, local_alarm_record_secs=30, callback=None
    ):
        """Set local alarm-record config`is_enable_local_alarm_record`: 0 disable, 1 enable."""
        params = {
            "isEnableLocalAlarmRecord": is_enable_local_alarm_record,
            "localAlarmRecordSecs": local_alarm_record_secs,
        }
        return self.execute_command(
            "setLocalAlarmRecordConfig", params, callback=callback
        )

    def get_h264_frm_ref_mode(self, callback=None):
        """Get grame shipping reference mode of H264 encode stream."""
        return self.execute_command("getH264FrmRefMode", callback=callback)

    def set_h264_frm_ref_mode(self, mode=1, callback=None):
        """Set frame shipping reference mode of H264 encode stream.params:`mode`: see docstr of meth::get_h264_frm_ref_mode."""
        params = {"mode": mode}
        return self.execute_command("setH264FrmRefMode", params, callback)

    def get_schedule_record_config(self, callback=None):
        """Get schedule record config."""
        return self.execute_command("getScheduleRecordConfig", callback=callback)

    def set_schedule_record_config(
        self,
        is_enable,
        record_level,
        space_full_mode,
        is_enable_audio,
        schedule0=0,
        schedule1=0,
        schedule2=0,
        schedule3=0,
        schedule4=0,
        schedule5=0,
        schedule6=0,
        callback=None,
    ):
        """Set schedule record config.cmd: setScheduleRecordConfigargs: See docstring of meth::get_schedule_record_config."""

        params = {
            "isEnable": is_enable,
            "isEnableAudio": is_enable_audio,
            "recordLevel": record_level,
            "spaceFullMode": space_full_mode,
            "schedule0": schedule0,
            "schedule1": schedule1,
            "schedule2": schedule2,
            "schedule3": schedule3,
            "schedule4": schedule4,
            "schedule5": schedule5,
            "schedule6": schedule6,
        }
        return self.execute_command(
            "setScheduleRecordConfig", params, callback=callback
        )

    def get_record_path(self, callback=None):
        """Get Record path: sd/ftp."""

        return self.execute_command("getRecordPath", callback=callback)

    def set_record_path(self, path, callback=None):
        """Set Record path: sd/ftp."""
        params = {"Path": path}
        return self.execute_command("setRecordPath", params, callback=callback)

    # *************** SnapPicture Function *******************

    def snap_picture_2(self, callback=None):
        """Manually request snapshot. Returns raw JPEG data.cmd: snapPicture2."""
        return self.execute_command("snapPicture2", {}, callback=callback, raw=True)

    # ******************* SMTP Functions *********************

    def set_smtp_config(self, params, callback=None):
        """Set smtp settings using the array of parameters."""
        return self.execute_command("setSMTPConfig", params, callback=callback)

    def get_smtp_config(self, callback=None):
        """Get smtp settings using the array of parameters."""
        return self.execute_command("getSMTPConfig", callback=callback)

    # ********************** Misc ****************************

    def get_log(self, offset, count=10, callback=None):
        """Retrieve log records from camera."""
        params = {"offset": offset, "count": count}
        return self.execute_command("getLog", params, callback=callback)

    def openWhiteLight(self, count=10, callback=None):
        """Turn on the camera white light."""
        return self.execute_command("openWhiteLight", callback=callback)

    def closeWhiteLight(self, ocount=10, callback=None):
        """Turn off the camera white light."""
        return self.execute_command("closeWhiteLight", callback=callback)

    def getWhiteLightBrightness(self, count=10, callback=None):
        """Get camera white light config."""
        return self.execute_command("getWhiteLightBrightness", callback=callback)

    def getSirenConfig(self, count=10, callback=None):
        """Get the siren alarm status."""
        return self.execute_command("getSirenConfig", callback=callback)

    def setSirenConfig(
        self, sirenEnable, sirenvolume, reserved, count=10, callback=None
    ):
        """Set siren alarm status."""
        params = {
            "sirenEnable": sirenEnable,
            "sirenvolume": sirenvolume,
            "reserved": reserved,
        }
        return self.execute_command("setSirenConfig", params, callback=callback)

    def getAudioVolume(self, count=10, callback=None):
        """Get Volume."""
        return self.execute_command("getAudioVolume", callback=callback)

    def setAudioVolume(self, volume, count=10, callback=None):
        """Set Volume."""
        params = {
            "volume": volume,
        }
        return self.execute_command("setAudioVolume", params, callback=callback)

    def getSpeakVolume(self, count=10, callback=None):
        """Get Speak Volume."""
        return self.execute_command("getSpeakVolume", callback=callback)

    def setSpeakVolume(self, SpeakVolume, count=10, callback=None):
        """Set Speak Volume."""
        params = {
            "SpeakVolume": SpeakVolume,
        }
        return self.execute_command("setSpeakVolume", params, callback=callback)

    def getVoiceEnableState(self, count=10, callback=None):
        """Get Turn off Volume Switch Status."""
        return self.execute_command("getVoiceEnableState", callback=callback)

    def setVoiceEnableState(self, isEnable, count=10, callback=None):
        """Set Turn off Volume Switch Status."""
        params = {
            "isEnable": isEnable,
        }
        return self.execute_command("setVoiceEnableState", params, callback=callback)

    def getLedEnableState(self, count=10, callback=None):
        """Get Led Switch Status."""
        return self.execute_command("getLedEnableState", callback=callback)

    def setLedEnableState(self, isEnable, count=10, callback=None):
        """Set Turn off Volume Switch Status."""
        params = {
            "isEnable": isEnable,
        }
        return self.execute_command("setLedEnableState", params, callback=callback)

    def setWdrMode(self, mode, count=10, callback=None):
        """Set WDR Switch Status."""
        params = {
            "mode": mode,
        }
        return self.execute_command("setWdrMode", params, callback=callback)

    def getWdrMode(self, count=10, callback=None):
        """Get WDR Switch Status."""
        return self.execute_command("getWdrMode", callback=callback)

    def setHdrMode(self, mode, count=10, callback=None):
        """Set HDR Switch Status."""
        params = {
            "mode": mode,
        }
        return self.execute_command("setHdrMode", params, callback=callback)

    def getHdrMode(self, count=10, callback=None):
        """Get HDR Switch Status."""
        return self.execute_command("getHdrMode", callback=callback)

    def setAlarmHttpServer(self, AlarmUrl, count=10, callback=None):
        """Set Alarm Http Server."""
        params = {
            "AlarmUrl": AlarmUrl,
        }
        return self.execute_command("setAlarmHttpServer", params, callback=callback)
