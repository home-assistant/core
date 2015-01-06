#! /usr/bin/python

# nest.py -- a python interface to the Nest Thermostat
# by Scott M Baker, smbaker@gmail.com, http://www.smbaker.com/
#
# Adapted to Python 3 by Stefano Fiorini
#
# Usage:
#    'nest.py help' will tell you what to do and how to do it
#
# Licensing:
#    This is distributed under the Creative Commons 3.0 Non-commercial,
#    Attribution, Share-Alike license. You can use the code for noncommercial
#    purposes. You may NOT sell it. If you do use it, then you must make an
#    attribution to me (i.e. Include my name and thank me for the hours I spent
#    on this)
#
# Acknowledgements:
#    Chris Burris's Siri Nest Proxy was very helpful to learn the nest's
#       authentication and some bits of the protocol.

import time
import codecs
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import sys
import re
import ssl
import http.client, socket
from optparse import OptionParser

try:
    import json
except ImportError:
   try:
       import simplejson as json
   except ImportError:
       print ("No json library available. I recommend installing either python-json")
       print ("or simplejson. Python 2.6+ contains json library already.")
       sys.exit(-1)

#force connection to be TLSv1
class HTTPSConnectionV1(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        http.client.HTTPSConnection.__init__(self, *args, **kwargs)

    def connect(self):
        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=ssl.PROTOCOL_TLSv1)

class HTTPSHandlerV1(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(HTTPSConnectionV1, req)
# install opener
urllib.request.install_opener(urllib.request.build_opener(HTTPSHandlerV1()))

class Nest:
    def __init__(self, username, password, serial=None, index=0, units="F", debug=False):
        self.username = username
        self.password = password
        self.serial = serial
        self.units = units
        self.index = index
        self.debug = debug
        self.headers={"user-agent":"Nest/1.1.0.10 CFNetwork/548.0.4",
                      "X-nl-protocol-version": "1"}
    def loads2(self, res):
        binary_data = res.decode("utf-8")
        return json.loads(binary_data)

    def loads(self, res):
        reader = codecs.getreader("utf-8")
        if hasattr(json, "loads"):
            res = json.loads(reader(res))
        else:
            res = json.read(reader(res))
        return res

    # context ['shared','structure','device']
    def handle_put(self, context, data):
        assert context is not None, "Context must be set to ['shared','structure','device']"
        assert data is not None, "Data is None"

        new_url = self.transport_url + "/v2/put/" + context + "."

        if (context == "shared" or context == "device"):
            new_url += self.serial
        elif (context == "structure"):
            new_url += self.structure_id
        else:
            raise ValueError(context+ " is unsupported")

        binary_data = data.encode("utf-8")
        req = urllib.request.Request(new_url, binary_data, self.headers)

        try:
            urllib.request.urlopen(req).read()
        except urllib.error.URLError:
            print ("Put operation failed")
            if (self.debug):
                print (new_url)
                print (data)

    def shared_put(self, data):
        self.handle_put("shared", data)

    def device_put(self, data):
        self.handle_put("device", data)

    def structure_put(self, data):
        self.handle_put("structure", data)

    def login(self):
        data = urllib.parse.urlencode({"username": self.username, "password": self.password})

        binary_data = data.encode("utf-8")
        req = urllib.request.Request("https://home.nest.com/user/login",
                              binary_data, self.headers)

        res = urllib.request.urlopen(req).read()

        res = self.loads2(res)

        self.transport_url = res["urls"]["transport_url"]
        self.userid = res["userid"]
        self.headers["Authorization"] = "Basic " + res["access_token"]
        self.headers["X-nl-user-id"]= self.userid

    def get_status(self):
        req = urllib.request.Request(self.transport_url + "/v2/mobile/user." + self.userid,
                              headers=self.headers)

        res = urllib.request.urlopen(req).read()

        res = self.loads2(res)

        self.structure_id = list(res["structure"].keys())[0]

        if (self.serial is None):
            self.device_id = res["structure"][self.structure_id]["devices"][self.index]
            self.serial = self.device_id.split(".")[1]

        self.status = res

        #print ("res.keys", res.keys())
        #print "res[structure][structure_id].keys", res["structure"][self.structure_id].keys()
        #print "res[device].keys", res["device"].keys()
        #print "res[device][serial].keys", res["device"][self.serial].keys()
        #print "res[shared][serial].keys", res["shared"][self.serial].keys()

    def temp_in(self, temp):
        if (self.units == "F"):
            return (temp - 32.0) / 1.8
        else:
            return temp

    def temp_out(self, temp):
        if (self.units == "F"):
            return temp*1.8 + 32.0
        else:
            return temp

    def show_status(self):
        shared = self.status["shared"][self.serial]
        device = self.status["device"][self.serial]
        structure = self.status["structure"][self.structure_id]

	# Delete the structure name so that we preserve the device name
        del structure["name"]
        allvars = shared

        allvars.update(structure)
        allvars.update(device)

        for k, v in sorted(allvars.items()):
           print((k + "."*(32-len(k)) + ":", self.format_value(k, v)))

    def format_value(self, key, value):
        if 'temp' in key and isinstance(value, float) and self.units == 'F':
            return '%s (%s F)' % (value, self.temp_out(value))

        elif 'timestamp' in key or key == 'creation_time':
            if value > 0xffffffff:
                value /= 1000
            return time.ctime(value) 

        elif key == 'mac_address' and len(value) == 12:
            return ':'.join(value[i:i+2] for i in range(0, 12, 2))

        else:
            return str(value)

    def get_units(self):
        return self.units

    def get_tartemp(self):
        temp = self.status["shared"][self.serial]["target_temperature"]
        temp = self.temp_out(temp)
        temp = ("%0.0f" % temp)

        return temp

    def get_curtemp(self):
        temp = self.status["shared"][self.serial]["current_temperature"]
        temp = self.temp_out(temp)
        temp = ("%0.1f" % temp)

        return temp

    def show_curtemp(self):
        print(self.get_curtemp())

    def is_away(self):
        return self.status["structure"][self.structure_id]["away"]

    def set_temperature(self, temp):
        temp = self.temp_in(temp)
        data = '{"target_change_pending":true,"target_temperature":' + '%0.1f' % temp + '}'
        self.shared_put(data)

    def set_fan(self, state):
        data = '{"fan_mode":"' + str(state) + '"}'
        self.device_put(data)

    def set_mode(self, state):
        data = '{"target_temperature_type":"' + str(state) + '"}'
        self.shared_put(data)

    def set_away(self, state):
        time_since_epoch   = time.time()
        if (state == "away"):
            data = '{"away_timestamp":' + str(time_since_epoch) + ',"away":true,"away_setter":0}'
        else:
            data = '{"away_timestamp":' + str(time_since_epoch) + ',"away":false,"away_setter":0}'

        self.structure_put(data)

    def set_auto_away(self, state):
        if (state == "enable"):
            data = '{"auto_away_enable":true}'
        else:
            data = '{"auto_away_enable":false}'
        self.device_put(data)

def create_parser():
   parser = OptionParser(usage="nest [options] command [command_options] [command_args]",
        description="Commands: fan temp mode away auto-away",
        version="unknown")

   parser.add_option("-u", "--user", dest="user",
                     help="username for nest.com", metavar="USER", default=None)

   parser.add_option("-p", "--password", dest="password",
                     help="password for nest.com", metavar="PASSWORD", default=None)

   parser.add_option("-c", "--celsius", dest="celsius", action="store_true", default=False,
                     help="use celsius instead of farenheit")

   parser.add_option("-s", "--serial", dest="serial", default=None,
                     help="optional, specify serial number of nest thermostat to talk to")

   parser.add_option("-d", "--debug", dest="debug", action="store_true", default=False,
                     help="Print debug information")

   parser.add_option("-i", "--index", dest="index", default=0, type="int",
                     help="optional, specify index number of nest to talk to")

   return parser

def help():
    print ("syntax: nest [options] command [command_args]")
    print ("options:")
    print ("   --user <username>          ... username on nest.com")
    print ("   --password <password>      ... password on nest.com")
    print ("   --celsius                  ... use celsius (the default is farenheit)")
    print ("   --serial <number>          ... optional, specify serial number of nest to use")
    print ("   --index <number>           ... optional, 0-based index of nest")
    print ("                                    (use --serial or --index, but not both)")
    print ()
    print ("commands: temp, fan, away, mode, show, curtemp, curhumid")
    print ("    temp <temperature>        ... set target temperature")
    print ("    fan [auto|on]             ... set fan state")
    print ("    away [away|here]          ... set away state")
    print ("    auto-away [enable|disable]... enable or disable auto away")
    print ("    mode [heat|cool|range]    ... set thermostat mode")
    print ("    show                      ... show everything")
    print ("    curtemp                   ... print current temperature")
    print ("    curhumid                  ... print current humidity")
    print ()
    print ("examples:")
    print ("    nest.py --user joe@user.com --password swordfish temp 73")
    print ("    nest.py --user joe@user.com --password swordfish fan auto")

def validate_temp(temp):
        try: 
            new_temp = float(temp)
        except ValueError:
            return -1
        if new_temp < 50 or new_temp > 90:
            return -1
        return new_temp
            
def main():
    parser = create_parser()
    (opts, args) = parser.parse_args()

    if (len(args)==0) or (args[0]=="help"):
        help()
        sys.exit(-1)

    if (not opts.user) or (not opts.password):
        print ("how about specifying a --user and --password option next time?")
        sys.exit(-1)

    if opts.celsius:
        units = "C"
    else:
        units = "F"

    n = Nest(opts.user, opts.password, opts.serial, opts.index, units=units, debug=opts.debug)
    n.login()
    n.get_status()

    cmd = args[0]

    if (cmd == "temp"):
        new_temp = -1
        if len(args)>1:
            new_temp = validate_temp(args[1])
        if new_temp == -1:
            print ("please specify a temperature between 50 and 90")
            sys.exit(-1)
        n.set_temperature(new_temp)
    elif (cmd == "fan"):
        if len(args)<2 or args[1] not in {"on", "auto"}:
            print ("please specify a fan state of 'on' or 'auto'")
            sys.exit(-1)
        n.set_fan(args[1])
    elif (cmd == "mode"):
        if len(args)<2 or args[1] not in {"cool", "heat", "range"}:
            print ("please specify a thermostat mode of 'cool', 'heat'  or 'range'")
            sys.exit(-1)
        n.set_mode(args[1])
    elif (cmd == "show"):
        n.show_status()
    elif (cmd == "curtemp"):
        n.show_curtemp()
    elif (cmd == "curhumid"):
        print((n.status["device"][n.serial]["current_humidity"]))
    elif (cmd == "away"):
        if len(args)<2 or args[1] not in {"away", "here"}:
            print ("please specify a state of 'away' or 'here'")
            sys.exit(-1)
        n.set_away(args[1])
    elif (cmd == "auto-away"):
        if len(args)<2 or args[1] not in {"enable", "disable"}:
            print ("please specify a state of 'enable' or 'disable'")
            sys.exit(-1)
        n.set_auto_away(args[1])
    else:
        print(("misunderstood command:", cmd))
        print ("do 'nest.py help' for help")

if __name__=="__main__":
   main()
