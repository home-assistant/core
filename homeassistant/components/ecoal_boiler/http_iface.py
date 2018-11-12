import datetime
import logging
import time

import requests
import requests.auth

global_log = logging.getLogger(__name__)
global_log.setLevel(logging.DEBUG)

class ECoalControler:
    CRCTABLE = (0, 49, 98, 83, 196, 245,166, 151,185, 136,219, 234,125, 76, 31, 46, 67, 114,33, 16,
                135, 182,229, 212,250, 203,152, 169,62, 15, 92, 109,134, 183,228, 213,66, 115,32, 17,
                63, 14, 93, 108,251, 202,153, 168,197, 244,167, 150,1, 48, 99, 82, 124, 77, 30, 47,
                184, 137,218, 235,61, 12, 95, 110,249, 200,155, 170,132, 181,230, 215,64, 113,34, 19,
                126, 79, 28, 45, 186, 139,216, 233,199, 246,165, 148,3, 50, 97, 80, 187, 138,217, 232,
                127, 78, 29, 44, 2, 51, 96, 81, 198, 247,164, 149,248, 201,154, 171,60, 13, 94, 111,
                65, 112,35, 18, 133, 180,231, 214,122, 75, 24, 41, 190, 143,220, 237,195, 242,161, 144,
                7, 54, 101, 84, 57, 8, 91, 106,253, 204,159, 174,128, 177,226, 211,68, 117,38, 23,
                252, 205,158, 175,56, 9, 90, 107,69, 116,39, 22, 129, 176,227, 210,191, 142,221, 236,
                123, 74, 25, 40, 6, 55, 100, 85, 194, 243,160, 145,71, 118,37, 20, 131, 178,225, 208,
                254, 207,156, 173,58, 11, 88, 105,4, 53, 102, 87, 192, 241,162, 147,189, 140,223, 238,
                121, 72, 27, 42, 193, 240,163, 146,5, 52, 103, 86, 120, 73, 26, 43, 188, 141,222, 239,
                130, 179,224, 209,70, 119,36, 21, 59, 10, 89, 104,255, 206,157, 172)

    class Status:
        mode_auto = None  # on/off

        internal_temp = None
        internal2_temp = None
        external_temp = None
        domestic_hot_water_temp = None
        target_domestic_hot_water_temp = None
        feedwater_in_temp = None
        feedwater_out_temp = None
        target_feedwater_temp = None
        coal_feeder_temp = None
        chimney_temp = None

        central_heating_pump = None # on/off
        domestic_hot_water_pump = None # on/off
        coal_feeder = None # on/off
        feeder_work_time = None # seconds
        air_pump = None # on/off
        air_pump_power = None # perc

        datetime = None

        def __str__(self):
            if self.mode_auto is None:
                return "N/A"
            txt = ""
            if self.mode_auto:
                txt += " auto"
            else:
                txt += " manual"
            txt += " external: %.1f°C" % (self.external_temp, )
            txt += " internal: %.1f°C %.1f°C" % (self.internal_temp, self.internal2_temp, )
            txt += " DHW: %.1f°C (target: %.1f°C)" % (self.domestic_hot_water_temp, self.target_domestic_hot_water_temp, )
            txt += " feedwater: %.1f°C -> %.1f°C (target: %.1f°C)" % (self.feedwater_in_temp, self.feedwater_out_temp, self.target_feedwater_temp)
            txt += " chimney: %.1f°C" % (self.chimney_temp, )
            if self.central_heating_pump:
                txt += " CH:On"
            else:
                txt += " CH:Off"
            if self.domestic_hot_water_pump:
                txt += " DHW:On"
            else:
                txt += " DHW:Off"
            if self.secondary_central_heating_pump:
                txt += " CH2:On"
            else:
                txt += " CH2:Off"
            if self.coal_feeder:
                txt += " Feeder:On"
            else:
                txt += " Feeder:Off"
            txt += " Feeder work time: %ds temp: %.1f°C" % (self.feeder_work_time, self.coal_feeder_temp)
            if self.air_pump:
                txt += " Air (%d%%):On" % (self.air_pump_power)
            else:
                txt += " Air (%d%%):Off" % (self.air_pump_power)  # Seems always be 0 if off ?
            ## txt += " %02d:%02d:%02d" % (self.hours, self.minutes, self.seconds, )
            txt += " %s" % (self.datetime, )
            return txt


    def __init__(self, host, login,  password, log=global_log):
        self.host = host
        self.login = login
        self.password = password
        self.requests_auth=requests.auth.HTTPBasicAuth(self.login, self.password)
        self.log = log
        self.timeout = 3.0

        self.status = None
        self.status_time = 0

        self.version = None # "BRULI" / "ECOAL"
        self.get_version()


    def _calc_temp(self, hi, lo):
        return ((hi<<8|lo)-(hi>>7<<16))/10.0


    def _get_request(self, req):
        ## r = requests.get('https://api.github.com/events')
        url = "http://%s/?com=%s" % (self.host, req)
        self.log.debug("_get_request(): request: %s" % (url, ) )
        resp = requests.get(url, timeout=self.timeout,  auth=self.requests_auth)

        if resp.status_code != 200:
            self.log.warn("Error quering controller: %s", resp)
        return resp


    def _parse_seq_of_ints(self, buf):
        start_pos = buf.find(b'[')
        end_pos = buf.find(b']')
        if start_pos < 0 or end_pos < 0  or start_pos >= end_pos:
            raise ValueError("Unable to parse as seqeuence of ints.", bytes)
        txt = buf[start_pos+1:end_pos]
        ## self.log.debug("txt: %r", txt)
        status_vals = []
        for val in txt.split(b','):
            try:
                val = int(val)
                status_vals.append(val)
            except:
                self.warn("Ints seqence failed to parse value: %r", val)
                status_vals.append(None)
        return status_vals


    def get_version(self):
        resp = self._get_request("0201000500020000A903")
        if resp.status_code != 200:
            return
        buf = resp.content
        # status: b'[2,1,6,6,0,0,76,0,0,0,0,0
        vals = self._parse_seq_of_ints(buf)

        if (vals[8:11] == [48, 46, 49]):
            self.version = "BRULI"
        elif (vals[8:11] == [48, 46, 51]):
            self.version = "ECOAL"
        else:
            self.version = None
        self.log.debug("Detected version: %r", self.version)
        return self.version



    def get_status(self):
        """Gets and parses controller status"""
        self.status = None
        resp = self._get_request("02010006000000006103")

        if resp.status_code != 200:
            return
        ## txt = str(resp.content);
        buf = resp.content
        # status: b'[2,1,6,6,0,0,76,0,0,0,0,0
        status_vals = self._parse_seq_of_ints(buf)
        self.log.debug("Receiveed status vals: %r", status_vals)

        old_status_vals = [2, 1, 6, 6, 0, 0, 76, 0, 0, 0, 0, 0, 0, 0, 0, 0, 215, 0, 214, 0, 103, 0, 165, 1, 163, 0, 155, 0, 219, 0, 165, 0, 0, 0, 0, 0, 2, 61, 48, 0, 0, 0, 2, 2, 18, 11, 11, 15, 13, 30, 1, 0, 0, 1, 0, 225, 0, 215, 0, 10, 8, 2, 0, 0, 195, 85, 0, 0, 18, 3, 17, 12, 5, 112, 81, 16, 0, 6, 225, 0, 210, 0, 0, 0, 36, 3]
        # 2018/11/11 diffs:
        # pos: 73 diff: 112 -> 113   pos: 84 diff: 36 -> 204

        for i, val in enumerate(status_vals):
            # Skip list of values we know about
            if i in (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 37, 38, 39, 44, 45, 46, 47, 48, 49, 64, 65   ):
                continue
            if val != old_status_vals[i]:
                self.log.debug("Diff pos: %d diff: %r -> %r", i, old_status_vals[i], val)

        # self.status_vals = status_vals
        status = self.Status()

        ## return self.__temp(self.s_statusdata[19],self.s_statusdata[18]);
        status.internal2_temp = self._calc_temp(status_vals[17],status_vals[16]) # Guess
        status.internal_temp = self._calc_temp(status_vals[19],status_vals[18])
        status.external_temp = self._calc_temp(status_vals[21],status_vals[20])
        status.domestic_hot_water_temp = self._calc_temp(status_vals[23],status_vals[22])
        status.feedwater_in_temp = self._calc_temp(status_vals[25],status_vals[24])
        status.coal_feeder_temp = self._calc_temp(status_vals[27],status_vals[26])
        status.feedwater_out_temp = self._calc_temp(status_vals[29],status_vals[28])
        status.chimney_temp = self._calc_temp(status_vals[31],status_vals[30])

        status.air_pump = status_vals[32] & (1 << 0) != 0
        status.coal_feeder = status_vals[32] & (1 << 1) != 0
        status.central_heating_pump = status_vals[32] & (1 << 2) != 0
        status.domestic_hot_water_pump = status_vals[32] & (1 << 3) != 0
        status.secondary_central_heating_pump = status_vals[32] & (1 << 4) != 0

        status.mode_auto = status_vals[34] == 1

        # DEBUG:__main__:Diff pos: 35 diff: 1 -> 0  # programator CO: 1 - pogodowy,  0 - programator CO ?
        status.target_feedwater_temp = status_vals[37]
        status.target_domestic_hot_water_temp = status_vals[38]
        status.air_pump_power = status_vals[39]

        status.datetime = datetime.datetime(2000+status_vals[44], status_vals[45], status_vals[46],
                            status_vals[47],  status_vals[48], status_vals[49])

        status.feeder_work_time =  (status_vals[65] << 8 | status_vals[64])

        self.status = status
        self.status_time = time.time()
        self.log.debug("New status: %s", self.status)
        return self.status


    def get_cached_status(self, max_cache_period=0.2):
        """
        Returns cached status if read less than max_cache_period.
        Otherwise fresh value is requested
        """
        if not self.status or time.time() - self.status_time > max_cache_period:
            self.get_status()
        return self.status

    def set_central_heating_pump(self, state):
        if state:
            resp = self._get_request("02010005000D0100018D03")
        else:
            resp = self._get_request("02010005000D010000BC03")

        if resp.status_code == 200 :
            return None
        self.warn("set_central_heating_pump() failed: %s", resp)
        return resp

    def set_central_heating_pump2(self, state):
        """ third pump can be configured as mixing feedwater pump,
        domestic hot water pump or 2nd heating pump
        """
        if state:
            v = 1
            # 02010005000f0100018a03
        else:
            v = 0
            # 02010005000f010000bb03
        buf = [0x01, 0x00, 0x05, 0x00, 0x0F, 0x01, 0x00, v , ]
        resp = self._calc_crc_get_request(buf)
        if resp.status_code == 200 :
            return None
        self.warn("set_central_heating_pump2() failed: %s", resp)
        return resp

    def set_domestic_hot_water_pump(self, state):
        if state:
            resp = self._get_request("02010005000E0100011103")
        else:
            resp = self._get_request("02010005000E0100002003")
        if resp.status_code == 200 :
            return None
        self.warn("set_domestic_hot_water_pump() failed: %s", resp)
        return resp

    def set_target_feedwater_temp(self, value):
        v = int(value)
        buf = [0x01, 0x00, 0x02, 0x00, 0x28, 0x02, 0x00, v & 0xff, 0x00];
        self._calc_crc_get_request(buf)

    def _calc_crc_get_request(self, buf):
        """
        Calculates CRC and expands buf command to be sent to controller
        """
        crc = self._calc_crc(buf);
        buf.insert(0, 0x02);
        buf.append(crc);
        buf.append(0x03);
        cmd = ''.join('{:02x}'.format(b) for b in buf);
        return self._get_request(cmd);


    def _calc_crc(self, buf):
        crc = 0
        for b in buf:
            crc = self.CRCTABLE[crc & 0xFF ^ b & 0xFF]
        return crc






if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG) # Basic setup.

    contr = ECoalControler("192.168.9.2", "admin", "admin")
    contr.get_cached_status()
    if 0:
        contr.get_cached_status()
        time.sleep(0.2)
        contr.get_cached_status()
    if 1:
        # contr.set_central_heating_pump(0)
        # contr.set_domestic_hot_water_pump(0)
        contr.set_central_heating_pump2(0)
        contr.get_status()

