#!/usr/bin/env python3
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from coapthon.client.helperclient import HelperClient
from coapthon import defines
from coapthon.messages.request import Request
from coapthon.utils import generate_random_token
import urllib.request
import base64
import binascii
import argparse
import json
import random
import os
import sys
import pprint
import configparser
import socket
import xml.etree.ElementTree as ET
import struct
import time
import logging

G = int('A4D1CBD5C3FD34126765A442EFB99905F8104DD258AC507FD6406CFF14266D31266FEA1E5C41564B777E690F5504F213160217B4B01B886A5E91547F9E2749F4D7FBD7D3B9A92EE1909D0D2263F80A76A6A24C087A091F531DBF0A0169B6A28AD662A4D18E73AFA32D779D5918D08BC8858F4DCEF97C2A24855E6EEB22B3B2E5', 16)
P = int('B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371', 16)

def aes_decrypt(data, key):
    iv = bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.decrypt(data)

def encrypt(values, key):
    # add two random bytes in front of the body
    data = 'AA' + json.dumps(values)
    data = pad(bytearray(data, 'ascii'), 16, style='pkcs7')
    iv = bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    data_enc = cipher.encrypt(data)
    return base64.b64encode(data_enc)

def decrypt(data, key):
    payload = base64.b64decode(data)
    data = aes_decrypt(payload, key)
    # response starts with 2 random bytes, exclude them
    response = unpad(data, 16, style='pkcs7')[2:]
    return response.decode('ascii')

class AirClient(object):

    @staticmethod
    def ssdp(timeout=1, repeats=3, debug=False):
        addr = '239.255.255.250'
        port = 1900
        msg = '\r\n'.join([
            'M-SEARCH * HTTP/1.1',
            'HOST: {}:{}'.format(addr, port),
            'ST: urn:philips-com:device:DiProduct:1',
            'MX: 1', 'MAN: "ssdp:discover"','', '']).encode('ascii')
        urls = {}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
            s.settimeout(timeout)
            for i in range(repeats):
                s.sendto(msg, (addr, port))
                try:
                    while True:
                        data, (ip, _) = s.recvfrom(1024)
                        url = next((x for x in data.decode('ascii').splitlines() if x.startswith('LOCATION: ')), None)
                        urls.update({ip: url[10:]})
                except socket.timeout:
                    pass
                if len(urls): break
        resp = []
        for ip in urls.keys():
            with urllib.request.urlopen(urls[ip]) as response:
                xml = ET.fromstring(response.read())
                resp.append({'ip': ip})
                ns = {'urn': 'urn:schemas-upnp-org:device-1-0'}
                for d in xml.findall('urn:device', ns):
                    for t in ['modelName', 'modelNumber', 'friendlyName']:
                        resp[-1].update({t: d.find('urn:'+t, ns).text})
        if debug:
            pprint.pprint(resp)
        return resp

    def __init__(self, host):
        self._host = host
        self._session_key = None

    def _get_key(self):
        print('Exchanging secret key with the device ...')
        url = 'http://{}/di/v1/products/0/security'.format(self._host)
        a = random.getrandbits(256)
        A = pow(G, a, P)
        data = json.dumps({'diffie': format(A, 'x')})
        data_enc = data.encode('ascii')
        req = urllib.request.Request(url=url, data=data_enc, method='PUT')
        with urllib.request.urlopen(req) as response:
            resp = response.read().decode('ascii')
            dh = json.loads(resp)
        key = dh['key']
        B = int(dh['hellman'], 16)
        s = pow(B, a, P)
        s_bytes = s.to_bytes(128, byteorder='big')[:16]
        session_key = aes_decrypt(bytes.fromhex(key), s_bytes)
        self._session_key = session_key[:16]
        self._save_key()

    def _save_key(self):
        config = configparser.ConfigParser()
        fpath = os.path.expanduser('~/.pyairctrl')
        config.read(fpath)
        if 'keys' not in config.sections():
            config['keys'] = {}
        hex_key = binascii.hexlify(self._session_key).decode('ascii')
        config['keys'][self._host] = hex_key
        print("Saving session_key {} to {}".format(hex_key, fpath))
        with open(fpath, 'w') as f:
            config.write(f)

    def load_key(self):
        fpath = os.path.expanduser('~/.pyairctrl')
        if os.path.isfile(fpath):
            config = configparser.ConfigParser()
            config.read(fpath)
            if 'keys' in config and self._host in config['keys']:
                hex_key = config['keys'][self._host]
                self._session_key = bytes.fromhex(hex_key)
                self._check_key()
            else:
                self._get_key()
        else:
            self._get_key()

    def _check_key(self):
        url = 'http://{}/di/v1/products/1/air'.format(self._host)
        self.get(url)

    def set_values(self, values, debug=False):
        body = encrypt(values, self._session_key)
        url = 'http://{}/di/v1/products/1/air'.format(self._host)
        req = urllib.request.Request(url=url, data=body, method='PUT')
        try:
            with urllib.request.urlopen(req) as response:
                resp = response.read()
                resp = decrypt(resp.decode('ascii'), self._session_key)
                status = json.loads(resp)
                self._dump_status(status, debug=debug)
        except urllib.error.HTTPError as e:
            print("Error setting values (response code: {})".format(e.code))


    def set_wifi(self, ssid, pwd):
        values = {}
        if ssid:
            values['ssid'] = ssid
        if pwd:
            values['password'] = pwd
        pprint.pprint(values)
        body = encrypt(values, self._session_key)
        url = 'http://{}/di/v1/products/0/wifi'.format(self._host)
        req = urllib.request.Request(url=url, data=body, method='PUT')
        with urllib.request.urlopen(req) as response:
            resp = response.read()
            resp = decrypt(resp.decode('ascii'), self._session_key)
            wifi = json.loads(resp)
            pprint.pprint(wifi)

    def _get_once(self, url):
        with urllib.request.urlopen(url) as response:
            resp = response.read()
            resp = decrypt(resp.decode('ascii'), self._session_key)
            return json.loads(resp)

    def get(self, url):
        try:
            return self._get_once(url)
        except Exception as e:
            print("GET error: {}".format(str(e)))
            print("Will retry after getting a new key ...")
            self._get_key()
            return self._get_once(url)

    def _dump_status(self, status, debug=False):
        if debug:
            pprint.pprint(status)
            print()
        if 'pwr' in status:
            pwr = status['pwr']
            pwr_str = {'1': 'ON', '0': 'OFF'}
            pwr = pwr_str.get(pwr, pwr)
            print('[pwr]   Power: {}'.format(pwr))
        if 'pm25' in status:
            pm25 = status['pm25']
            print('[pm25]  PM25: {}'.format(pm25))
        if 'rh' in status:
            rh = status['rh']
            print('[rh]    Humidity: {}'.format(rh))
        if 'rhset' in status:
            rhset = status['rhset']
            print('[rhset] Target humidity: {}'.format(rhset))
        if 'iaql' in status:
            iaql = status['iaql']
            print('[iaql]  Allergen index: {}'.format(iaql))
        if 'temp' in status:
            temp = status['temp']
            print('[temp]  Temperature: {}'.format(temp))
        if 'func' in status:
            func = status['func']
            func_str = {'P': 'Purification', 'PH': 'Purification & Humidification'}
            func = func_str.get(func, func)
            print('[func]  Function: {}'.format(func))
        if 'mode' in status:
            mode = status['mode']
            mode_str = {'P': 'auto', 'A': 'allergen', 'S': 'sleep', 'M': 'manual', 'B': 'bacteria', 'N': 'night'}
            mode = mode_str.get(mode, mode)
            print('[mode]  Mode: {}'.format(mode))
        if 'om' in status:
            om = status['om']
            om_str = {'s': 'silent', 't': 'turbo'}
            om = om_str.get(om, om)
            print('[om]    Fan speed: {}'.format(om))
        if 'aqil' in status:
            aqil = status['aqil']
            print('[aqil]  Light brightness: {}'.format(aqil))
        if 'uil' in status:
            uil = status['uil']
            uil_str = {'1': 'ON', '0': 'OFF'}
            uil = uil_str.get(uil, uil)
            print('[uil]   Buttons light: {}'.format(uil))
        if 'ddp' in status:
            ddp = status['ddp']
            ddp_str = {'1': 'PM2.5', '0': 'IAI'}
            ddp = ddp_str.get(ddp, ddp)
            print('[ddp]   Used index: {}'.format(ddp))
        if 'wl' in status:
            wl = status['wl']
            print('[wl]    Water level: {}'.format(wl))
        if 'cl' in status:
            cl = status['cl']
            print('[cl]    Child lock: {}'.format(cl))
        if 'dt' in status:
            dt = status['dt']
            if dt != 0:
                print('[dt]    Timer: {} hours'.format(dt))
        if 'dtrs' in status:
            dtrs = status['dtrs']
            if dtrs != 0:
                print('[dtrs]  Timer: {} minutes left'.format(dtrs))
        if 'err' in status:
            err = status['err']
            if err != 0:
                err_str = {49408: 'no water', 32768: 'water tank open', 49155: 'pre-filter must be cleaned'}
                err = err_str.get(err, err)
                print('-'*20)
                print('Error: {}'.format(err))

    def get_status(self, debug=False):
        url = 'http://{}/di/v1/products/1/air'.format(self._host)
        status = self.get(url)
        self._dump_status(status, debug=debug)

    def get_wifi(self):
        url = 'http://{}/di/v1/products/0/wifi'.format(self._host)
        wifi = self.get(url)
        pprint.pprint(wifi)

    def get_firmware(self):
        url = 'http://{}/di/v1/products/0/firmware'.format(self._host)
        firmware = self.get(url)
        pprint.pprint(firmware)

    def get_filters(self):
        url = 'http://{}/di/v1/products/1/fltsts'.format(self._host)
        filters = self.get(url)
        print('Pre-filter and Wick: clean in {} hours'.format(filters['fltsts0']))
        if 'wicksts' in filters:
            print('Wick filter: replace in {} hours'.format(filters['wicksts']))
        print('Active carbon filter: replace in {} hours'.format(filters['fltsts2']))
        print('HEPA filter: replace in {} hours'.format(filters['fltsts1']))

    def pair(self, client_id, client_secret):
        values = {}
        values['Pair'] = ['FI-AIR-AND', client_id, client_secret]
        body = encrypt(values, self._session_key)
        url = 'http://{}/di/v1/products/0/pairing'.format(self._host)
        req = urllib.request.Request(url=url, data=body, method='PUT')
        with urllib.request.urlopen(req) as response:
            resp = response.read()
            resp = decrypt(resp.decode('ascii'), self._session_key)
            resp = json.loads(resp)
            pprint.pprint(resp)


class AirClient2:
    def __init__(self, host, port = 5683):
        self.coapthon_logger = logging.getLogger("coapthon")
        self.coapthon_logger.setLevel("WARN")
        self.server = host
        self.port = port

    def _create_coap_client(self, host, port):
        return HelperClient(server=(host, port))

    def _send_over_socket(self, destination, packet):
        protocol = socket.getprotobyname('icmp')
        if os.geteuid()==0:
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, protocol)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, protocol)
        try:
            s.sendto(packet, (destination, 0))
        except OSError: # That fixes a mac os bug for me: OSError: [Errno 22] Invalid argument
            None
        finally:
            s.close()

    def get(self):
        path ="/sys/dev/status"
        try:
            client = self._create_coap_client(self.server, self.port)
            self._send_hello_sequence(client)
            request = client.mk_request(defines.Codes.GET, path)
            request.destination = server=(self.server, self.port)
            request.type = defines.Types["ACK"]
            request.token = generate_random_token(4)
            request.observe = 0
            response = client.send_request(request, None, 2)
        finally:
            client.stop()

        if response:
            return json.loads(response.payload)["state"]["reported"]
        else:
            return {}

    def set(self, key, value):
        path = "/sys/dev/control"
        try:
            client = self._create_coap_client(self.server, self.port)
            self._send_hello_sequence(client)
            payload = { "state" : { "desired" : { key: value } } }
            client.post(path, json.dumps(payload))
        finally:
            client.stop()


    def _send_hello_sequence(self, client):
        own_ip = self._get_ip()

        header = self._create_icmp_header()
        data = self._create_icmp_data(own_ip, self.port, self.server, self.port)
        packet = header + data
        packet = self._create_icmp_header(self._checksum_icmp(packet)) + data

        self._send_over_socket(self.server, packet)

        # that is needed to give device time to open coap port, otherwise it may not respond properly
        time.sleep(0.2)

        request = Request()
        request.destination = (self.server, self.port)
        request.code = defines.Codes.EMPTY.number
        client.send_empty(request)


    def _get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def _checksum_icmp(self, source_string):
        countTo = (int(len(source_string) / 2)) * 2
        sum = 0
        count = 0
        loByte = 0
        hiByte = 0
        while count < countTo:
            if (sys.byteorder == "little"):
                loByte = source_string[count]
                hiByte = source_string[count + 1]
            else:
                loByte = source_string[count + 1]
                hiByte = source_string[count]
            sum = sum + (hiByte * 256 + loByte)
            count += 2

        if countTo < len(source_string): # Check for odd length
            loByte = source_string[len(source_string) - 1]
            sum += loByte

        sum &= 0xffffffff
        sum = (sum >> 16) + (sum & 0xffff)
        sum += (sum >> 16)
        answer = ~sum & 0xffff
        answer = socket.htons(answer)
        return answer

    def _create_icmp_header(self, checksum=0):
        ICMP_TYPE = 3
        ICMP_CODE = 3
        UNUSED = 0
        CHECKSUM = checksum
        header = struct.pack(
            "!BBHI", ICMP_TYPE, ICMP_CODE, CHECKSUM, UNUSED
        )
        return header

    def _checksum_tcp(self, pkt):
        return 0 # looks like its irrelevant what we send here

    def _create_tcp_data(self, srcIp, dstIp, checksum=0):
        ip_version = 4
        ip_vhl = 5

        ip_ver = (ip_version << 4 ) + ip_vhl

        # Differentiate Service Field
        ip_dsc = 0
        ip_ecn = 0

        ip_dfc = (ip_dsc << 2 ) + ip_ecn

        # Total Length
        ip_tol = 214

        # Identification
        ip_idf = 6190

        # Flags
        ip_rsv = 0
        ip_dtf = 0
        ip_mrf = 0
        ip_frag_offset = 0

        ip_flg = (ip_rsv << 7) + (ip_dtf << 6) + (ip_mrf << 5) + (ip_frag_offset)

        # Time to live
        ip_ttl = 255

        # Protocol
        ip_proto = socket.IPPROTO_UDP

        # Check Sum
        ip_chk = checksum

        # Source Address
        ip_saddr = socket.inet_aton(srcIp)

        # Destination Address
        ip_daddr = socket.inet_aton(dstIp)
        tcp = struct.pack('!BBHHHBBH4s4s' ,
            ip_ver,   # IP Version
            ip_dfc,   # Differentiate Service Feild
            ip_tol,   # Total Length
            ip_idf,   # Identification
            ip_flg,   # Flags
            ip_ttl,   # Time to leave
            ip_proto, # protocol
            ip_chk,   # Checksum
            ip_saddr, # Source IP
            ip_daddr  # Destination IP
        )
        return tcp

    def _create_udp_data(self, srcPort, dstPort):
        data = 0
        sport = srcPort
        dport = dstPort
        length = 194
        checksum = 0
        udp = struct.pack('!HHHH', sport, dport, length, checksum)
        return udp

    def _create_icmp_data(self, srcIp, srcPort, dstIp, dstPort):
        return self._create_tcp_data(srcIp, dstIp) + self._create_udp_data(srcPort, dstPort)

    def _dump_status(self, status, debug=False):
        if debug==True:
            print("Raw status: " + str(status))
        if 'name' in status:
            name = status['name']
            print('[name]        Name: {}'.format(name))
        if 'modelid' in status:
            modelid = status['modelid']
            print('[modelid]     ModelId: {}'.format(modelid))
        if 'swversion' in status:
            swversion = status['swversion']
            print('[swversion]   Version: {}'.format(swversion))
        if 'StatusType' in status:
            statustype = status['StatusType']
            print('[StatusType]  StatusType: {}'.format(statustype))
        if 'ota' in status:
            ota = status['ota']
            print('[ota]         Over the air updates: {}'.format(ota))
        if 'Runtime' in status:
            runtime = status['Runtime']
            print('[Runtime]     Runtime: {} hours'.format(round(((runtime/(1000*60*60))%24), 2)))
        if 'pwr' in status:
            pwr = status['pwr']
            pwr_str = {'1': 'ON', '0': 'OFF'}
            pwr = pwr_str.get(pwr, pwr)
            print('[pwr]         Power: {}'.format(pwr))
        if 'pm25' in status:
            pm25 = status['pm25']
            print('[pm25]        PM25: {}'.format(pm25))
        if 'rh' in status:
            rh = status['rh']
            print('[rh]          Humidity: {}'.format(rh))
        if 'rhset' in status:
            rhset = status['rhset']
            print('[rhset]       Target humidity: {}'.format(rhset))
        if 'iaql' in status:
            iaql = status['iaql']
            print('[iaql]        Allergen index: {}'.format(iaql))
        if 'temp' in status:
            temp = status['temp']
            print('[temp]        Temperature: {}'.format(temp))
        if 'func' in status:
            func = status['func']
            func_str = {'P': 'Purification', 'PH': 'Purification & Humidification'}
            func = func_str.get(func, func)
            print('[func]        Function: {}'.format(func))
        if 'mode' in status:
            mode = status['mode']
            mode_str = {'P': 'auto', 'A': 'allergen', 'S': 'sleep', 'M': 'manual', 'B': 'bacteria', 'N': 'night'}
            mode = mode_str.get(mode, mode)
            print('[mode]        Mode: {}'.format(mode))
        if 'om' in status:
            om = status['om']
            om_str = {'s': 'silent', 't': 'turbo'}
            om = om_str.get(om, om)
            print('[om]          Fan speed: {}'.format(om))
        if 'aqil' in status:
            aqil = status['aqil']
            print('[aqil]        Light brightness: {}'.format(aqil))
        if 'uil' in status:
            uil = status['uil']
            uil_str = {'1': 'ON', '0': 'OFF'}
            uil = uil_str.get(uil, uil)
            print('[uil]         Buttons light: {}'.format(uil))
        if 'ddp' in status:
            ddp = status['ddp']
            ddp_str = {'3': 'Humidity', '1': 'PM2.5', '0': 'IAI'}
            ddp = ddp_str.get(ddp, ddp)
            print('[ddp]         Used index: {}'.format(ddp))
        if 'wl' in status:
            wl = status['wl']
            print('[wl]          Water level: {}'.format(wl))
        if 'cl' in status:
            cl = status['cl']
            print('[cl]          Child lock: {}'.format(cl))
        if 'dt' in status:
            dt = status['dt']
            if dt != 0:
                print('[dt]          Timer: {} hours'.format(dt))
        if 'dtrs' in status:
            dtrs = status['dtrs']
            if dtrs != 0:
                print('[dtrs]        Timer: {} minutes left'.format(dtrs))
        if 'fltsts0' in status:
            fltsts0 = status['fltsts0']
            print('[fltsts0]     Pre-filter and Wick: clean in {} hours'.format(fltsts0))
        if 'fltsts1' in status:
            fltsts1 = status['fltsts1']
            print('[fltsts1]     HEPA filter: replace in {} hours'.format(fltsts1))
        if 'fltsts2' in status:
            fltsts2 = status['fltsts2']
            print('[fltsts2]     Active carbon filter: replace in {} hours'.format(fltsts2))
        if 'wicksts' in status:
            wicksts = status['wicksts']
            print('[wicksts]     Wick filter: replace in {} hours'.format(wicksts))
        if 'err' in status:
            err = status['err']
            if err != 0:
                err_str = {49408: 'no water', 32768: 'water tank open', 49155: 'pre-filter must be cleaned'}
                err = err_str.get(err, err)
                print('-'*20)
                print('[ERROR] Message: {}'.format(err))

    def set_values(self, values, debug=False):
        if debug:
            self.coapthon_logger.setLevel("DEBUG")
        for key in values:
            self.set(key, values[key])

    def get_status(self, debug=False):
        if debug:
            self.coapthon_logger.setLevel("DEBUG")
        status = self.get()
        return self._dump_status(status, debug=debug)

    def get_wifi(self):
        print("Getting wifi credentials is currently not supported for protocol version 2 devices. Use the app instead.")

    def set_wifi(self, ssid, pwd):
        print("Setting wifi credentials is currently not supported for protocol version 2 devices. Use the app instead.")

    def get_firmware(self):
        status = self.get()
        print("Software version: {}".format(status["swversion"]))
        print("Over the air updates: {}".format(status["ota"]))

    def get_filters(self):
        status = self.get()
        print('Pre-filter and Wick: clean in {} hours'.format(status["fltsts0"]))
        print('HEPA filter: replace in {} hours'.format(status["fltsts1"]))
        print('Active carbon filter: replace in {} hours'.format(status["fltsts2"]))
        print('Wick filter: replace in {} hours'.format(status["wicksts"]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ipaddr', help='IP address of air purifier')
    parser.add_argument('--protocol', help='Switch from old to new protocol version for late 2019 devices and newer', choices=['1','2'], default='1')
    parser.add_argument('-d', '--debug', help='show debug output', action='store_true')
    parser.add_argument('--om', help='set fan speed', choices=['1','2','3','s','t'])
    parser.add_argument('--pwr', help='power on/off', choices=['0','1'])
    parser.add_argument('--mode', help='set mode', choices=['P','A','S','M','B','N'])
    parser.add_argument('--rhset', help='set target humidity', choices=['40','50','60','70'])
    parser.add_argument('--func', help='set function', choices=['P','PH'])
    parser.add_argument('--aqil', help='set light brightness', choices=['0','25','50','75','100'])
    parser.add_argument('--uil', help='set button lights on/off', choices=['0','1'])
    parser.add_argument('--ddp', help='set indicator pm2.5/IAI/Humidity (for protocol 2: IAI/pm2.5/Humidity)', choices=['0','1','3'])
    parser.add_argument('--dt', help='set timer', choices=['0','1','2','3','4','5','6','7','8','9','10','11','12'])
    parser.add_argument('--cl', help='set child lock', choices=['True','False'])
    parser.add_argument('--wifi', help='read wifi options', action='store_true')
    parser.add_argument('--wifi-ssid', help='set wifi ssid')
    parser.add_argument('--wifi-pwd', help='set wifi password')
    parser.add_argument('--firmware', help='read firmware', action='store_true')
    parser.add_argument('--filters', help='read filters status', action='store_true')
    args = parser.parse_args()

    if args.ipaddr:
        devices = [ {'ip': args.ipaddr} ]
    else:
        if args.protocol == 2:
            print('New Air purifiers cannot be autodetected. Try --ipaddr option to force specific IP address.')
            sys.exit(1)

        devices = AirClient.ssdp(debug=args.debug)
        if not devices:
            print('Air purifier not autodetected. Try --ipaddr option to force specific IP address.')
            sys.exit(1)

    for device in devices:
        if args.protocol == 1:
            c = AirClient(device['ip'])
            c.load_key()
        else:
            c = AirClient2(device['ip'])

        if args.wifi:
            c.get_wifi()
            sys.exit(0)
        if args.firmware:
            c.get_firmware()
            sys.exit(0)
        if args.wifi_ssid or args.wifi_pwd:
            c.set_wifi(args.wifi_ssid, args.wifi_pwd)
            sys.exit(0)
        if args.filters:
            c.get_filters()
            sys.exit(0)

        values = {}
        if args.om:
            values['om'] = args.om
        if args.pwr:
            values['pwr'] = args.pwr
        if args.mode:
            values['mode'] = args.mode
        if args.rhset:
            values['rhset'] = int(args.rhset)
        if args.func:
            values['func'] = args.func
        if args.aqil:
            values['aqil'] = int(args.aqil)
        if args.ddp:
            values['ddp'] = args.ddp
        if args.uil:
            values['uil'] = args.uil
        if args.dt:
            values['dt'] = int(args.dt)
        if args.cl:
            values['cl'] = (args.cl == 'True')

        if values:
            c.set_values(values, debug=args.debug)
        else:
            c.get_status(debug=args.debug)


if __name__ == '__main__':
    main()