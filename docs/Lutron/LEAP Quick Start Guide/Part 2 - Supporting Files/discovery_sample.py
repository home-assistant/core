# This shows you how to find the Lutron processor using bonjour.
# This file is not to be used in shipping software. 
# Run pip install zeroconf for python-zeroconf
# (c) Lutron Electronics Co. Inc. 2023. All rights reserved

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import time

from zeroconf._core import Zeroconf

class MyListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        server = info.server
        ipaddr = info._ipv4_addresses[0]
        systype = info.properties[b'SYSTYPE'].decode("ASCII")
        sernum = info.properties[b'SERNUM'].decode("ASCII")
        claimed = info.properties[b'CLAIM_STATUS'].decode("ASCII")
        version = info.properties[b'CODEVER'].decode("ASCII")
        mac = info.properties[b'MACADDR'].decode("ASCII")
        print(f"  Server: {server}, IPv4: {ipaddr}, System: {systype}, Serial: {sernum}, MAC: {mac}, Claimed: {claimed}, Sw version: {version}")
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:  # e.g. when two procs report the same service "Lutron Service"
        info = zc.get_service_info(type_, name)
        server = info.server
        ipaddr = info._ipv4_addresses[0]
        systype = info.properties[b'SYSTYPE'].decode("ASCII")
        sernum = info.properties[b'SERNUM'].decode("ASCII")
        claimed = info.properties[b'CLAIM_STATUS'].decode("ASCII")
        version = info.properties[b'CODEVER'].decode("ASCII")
        mac = info.properties[b'MACADDR'].decode("ASCII")
        print(f"  Server: {server}, IPv4: {ipaddr}, System: {systype}, Serial: {sernum}, MAC: {mac}, Claimed: {claimed}, Sw version: {version}")
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

zeroconf = Zeroconf()
listener = MyListener()
browser = ServiceBrowser(zeroconf, "_lutron._tcp.local.", listener)
try:
    print("Searching for Lutron processors (5s)")
    time.sleep(5)
finally:
    zeroconf.close()