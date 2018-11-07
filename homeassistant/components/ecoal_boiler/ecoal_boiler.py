import logging
import requests
import requests.auth

global_log = logging.getLogger(__name__)
global_log.setLevel(logging.DEBUG)

class ECoalControler:
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

        hours = None
        minutes = None
        seconds = None

        def __str__(self):
            if self.mode_auto is None:
                return "N/A"
            txt = ""
            if self.mode_auto:
                txt += " auto"
            else:
                txt += " manual"
            txt += " internal: %.1f°C %.1f°C" % (self.internal_temp, self.internal2_temp, )
            txt += " DHW: %.1f°C (target: %.1f°C)" % (self.domestic_hot_water_temp, self.target_domestic_hot_water_temp, )
            txt += " coal: %.1f°C" % (self.coal_feeder_temp, )
            txt += " feedwater: %.1f°C -> %.1f°C (target: %.1f°C)" % (self.feedwater_in_temp, self.feedwater_out_temp, self.target_feedwater_temp)
            txt += " chimney: %.1f°C" % (self.chimney_temp, )
            txt += " external: %.1f°C" % (self.external_temp, )
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
            txt += " Feeder work time: %ds" % (self.feeder_work_time, )
            if self.air_pump:
                txt += " Air (%d%%):On" % (self.air_pump_power)
            else:
                txt += " Air (%d%%):Off" % (self.air_pump_power)  # Seems always be 0 if off ?
            txt += " %02d:%02d:%02d" % (self.hours, self.minutes, self.seconds, )
            return txt


    def __init__(self, host, login,  password, log=global_log):
        self.host = host
        self.login = login
        self.password = password
        self.requests_auth=requests.auth.HTTPBasicAuth(self.login, self.password)
        self.log = log
        self.timeout = 3.0



    def _calc_temp(self, hi, lo):
        return ((hi<<8|lo)-(hi>>7<<16))/10.0


    def _get_request(self, req):
        ## r = requests.get('https://api.github.com/events')
        url = "http://%s/?com=%s" % (self.host, req)
        self.log.debug("_get_request(): request: %s" % (url, ) )
        resp = requests.get(url, timeout=self.timeout,  auth=self.requests_auth)

        if resp.status_code != 200:
            self.log.warn("Error quering controller: %s", resp)
            ## return r.status_code
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


    def get_status(self):
        """Pobiera status ze sterownika i zapamiętuje go"""
        self.status = None
        resp = self._get_request("02010006000000006103")

        if resp.status_code != 200:
            return
        ## txt = str(resp.content);
        buf = resp.content
        # status: b'[2,1,6,6,0,0,76,0,0,0,0,0
        status_vals = self._parse_seq_of_ints(buf)
        self.log.debug("Receiveed status vals: %r", status_vals)

        old_status_vals = [2, 1, 6, 6, 0, 0, 76, 0, 0, 0, 0, 0, 0, 0, 0, 0, 214, 0, 211, 0, 98, 0, 95, 1, 166, 0, 159, 0, 204, 0, 170, 0, 0, 0, 0, 1, 2, 55, 48, 0, 0, 0, 2, 2, 18, 11, 7, 18, 54, 6, 1, 0, 0, 1, 0, 225, 0, 215, 0, 10, 8, 2, 0, 0, 195, 85, 0, 0, 18, 3, 17, 12, 5, 106, 55, 16, 0, 6, 225, 0, 210, 0, 0, 0, 49, 3]
        for i, val in enumerate(status_vals):
            # Skip list of values we know about
            if i in (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 37, 39, 47, 48, 49, 64, 65   ):
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
        ## temp = self._calc_temp(status_vals[49],status_vals[48])
        ## temp = self._calc_temp(status_vals[73],status_vals[72])
        ## temp = self._calc_temp(status_vals[85],status_vals[84])
        ## temp = self._calc_temp(status_vals[17],status_vals[16])
        ## self.log.debug("temp: %r", temp)

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

        # 47, 48, 49  # hour, minutes , seconds
        status.hours = status_vals[47]
        status.minutes = status_vals[48]
        status.seconds = status_vals[49]

        status.feeder_work_time =  (status_vals[65] << 8 | status_vals[64])

        self.status = status
        self.log.debug("New status: %s", self.status)

##        txt = txt[txt.index('[') + 1:txt.index(']')]
##        data = list(map(int, txt.split(',')));
##        self.s_statusdata = data;



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG) # Basic setup.

    contr = ECoalControler("192.168.9.2", "admin", "admin")
    contr.get_status()

