"""Simulate a DHCP discover packet from an Indevolt device for manual HA testing."""

import random

from scapy.all import BOOTP, DHCP, IP, UDP, Ether, sendp

MAC = "1c:78:4b:8d:47:bb"
DEVICE_IP = "192.168.2.30"  # IP the "device" is claiming
IFACE = "eth0"

raw_mac = bytes.fromhex(MAC.replace(":", ""))

pkt = (
    Ether(src=MAC, dst="ff:ff:ff:ff:ff:ff")
    / IP(src="0.0.0.0", dst="255.255.255.255")
    / UDP(sport=68, dport=67)
    / BOOTP(chaddr=raw_mac, xid=random.randint(0, 0xFFFFFFFF), ciaddr=DEVICE_IP)
    / DHCP(
        options=[
            ("message-type", "request"),
            ("requested_addr", DEVICE_IP),
            ("hostname", "indevolt"),
            "end",
        ]
    )
)

sendp(pkt, iface=IFACE, verbose=True)
