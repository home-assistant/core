"""Script to enter Broadlink RM devices in learning mode."""

import argparse


class Broadlink():
    """Broadlink connector class."""

    class Device:
        """Broadlink Device."""

        def __init__(self, host, mac):
            """Initialize the object."""
            import socket
            import random
            import threading
            self.host = host
            self.mac = mac
            self.count = random.randrange(0xffff)

            self.key = b'\x09\x76\x28\x34\x3f\xe9\x9e'\
                       b'\x23\x76\x5c\x15\x13\xac\xcf\x8b\x02'
            self.ivr = b'\x56\x2e\x17\x99\x6d\x09\x3d\x28\xdd'\
                       b'\xb3\xba\x69\x5a\x2e\x6f\x58'

            self.ip_arr = bytearray([0, 0, 0, 0])
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind(('', 0))
            self.lock = threading.Lock()

        def auth(self):
            """Obtain the authentication key."""
            from Crypto.Cipher import AES
            payload = bytearray(0x50)
            payload[0x04] = 0x31
            payload[0x05] = 0x31
            payload[0x06] = 0x31
            payload[0x07] = 0x31
            payload[0x08] = 0x31
            payload[0x09] = 0x31
            payload[0x0a] = 0x31
            payload[0x0b] = 0x31
            payload[0x0c] = 0x31
            payload[0x0d] = 0x31
            payload[0x0e] = 0x31
            payload[0x0f] = 0x31
            payload[0x10] = 0x31
            payload[0x11] = 0x31
            payload[0x12] = 0x31
            payload[0x1e] = 0x01
            payload[0x2d] = 0x01
            payload[0x30] = ord('T')
            payload[0x31] = ord('e')
            payload[0x32] = ord('s')
            payload[0x33] = ord('t')
            payload[0x34] = ord(' ')
            payload[0x35] = ord(' ')
            payload[0x36] = ord('1')

            response = self.send_packet(0x65, payload)

            enc_payload = response[0x38:]

            aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.ivr))
            payload = aes.decrypt(bytes(enc_payload))

            if payload:
                self.ip_arr = payload[0x00:0x04]
                self.key = payload[0x04:0x14]
                return True
            else:
                print('Connection to broadlink device has failed.')
                return False

        def send_packet(self, command, payload, timeout=5.0):
            """Send packet to Broadlink device."""
            import socket
            from Crypto.Cipher import AES
            try:
                packet = bytearray(0x38)
                packet[0x00] = 0x5a
                packet[0x01] = 0xa5
                packet[0x02] = 0xaa
                packet[0x03] = 0x55
                packet[0x04] = 0x5a
                packet[0x05] = 0xa5
                packet[0x06] = 0xaa
                packet[0x07] = 0x55
                packet[0x24] = 0x2a
                packet[0x25] = 0x27
                packet[0x26] = command
                packet[0x28] = self.count & 0xff
                packet[0x29] = self.count >> 8
                packet[0x2a] = self.mac[0]
                packet[0x2b] = self.mac[1]
                packet[0x2c] = self.mac[2]
                packet[0x2d] = self.mac[3]
                packet[0x2e] = self.mac[4]
                packet[0x2f] = self.mac[5]
                packet[0x30] = self.ip_arr[0]
                packet[0x31] = self.ip_arr[1]
                packet[0x32] = self.ip_arr[2]
                packet[0x33] = self.ip_arr[3]
            except (IndexError, TypeError, NameError):
                print('Invalid IP or MAC address.')
                return bytearray(0x30)

            checksum = 0xbeaf
            for i, _ in enumerate(payload):
                checksum += payload[i]
                checksum = checksum & 0xffff

            aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.ivr))
            payload = aes.encrypt(bytes(payload))

            packet[0x34] = checksum & 0xff
            packet[0x35] = checksum >> 8

            for i, _ in enumerate(payload):
                packet.append(payload[i])

            checksum = 0xbeaf
            for i, _ in enumerate(packet):
                checksum += packet[i]
                checksum = checksum & 0xffff
            packet[0x20] = checksum & 0xff
            packet[0x21] = checksum >> 8

            with self.lock:
                self.sock.sendto(packet, self.host)
                try:
                    self.sock.settimeout(timeout)
                    response = self.sock.recvfrom(1024)
                except socket.timeout:
                    print("Socket timeout...")
                    return bytearray(0x30)

            return response[0]

        def send_data(self, data):
            """Send an IR or RF packet."""
            packet = bytearray([0x02, 0x00, 0x00, 0x00])
            packet += data
            self.send_packet(0x6a, packet)

        def enter_learning(self):
            """Enter learning mode."""
            packet = bytearray(16)
            packet[0] = 3
            self.send_packet(0x6a, packet)

        def check_data(self):
            """Obtain the IR or RF packet."""
            from Crypto.Cipher import AES
            packet = bytearray(16)
            packet[0] = 4
            response = self.send_packet(0x6a, packet)
            err = response[0x22] | (response[0x23] << 8)
            if err == 0:
                aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.ivr))
                payload = aes.decrypt(bytes(response[0x38:]))
                return payload[0x04:]


def yesno(question, default="yes"):
    """Ask a yes/no question and return their answer."""
    import sys

    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def run(args):
    """Handle ensure config commandline script."""
    import base64
    import binascii

    parser = argparse.ArgumentParser(
        description="Put Broadlink RM device in learning mode")
    parser.add_argument(
        '--script',
        choices=['broadlink'])
    parser.add_argument(
        '-i', '--ip',
        default=None,
        help="Device IP address")
    parser.add_argument(
        '-m', '--mac',
        default=None,
        help="Device MAC address")

    args = parser.parse_args()

    if args.ip is None and args.mac is None:
        parser.print_help()
        return 1

    ip_addr = (args.ip, 80)
    mac_addr = binascii.unhexlify(args.mac.encode().replace(b':', b''))
    device = Broadlink.Device(host=ip_addr, mac=mac_addr)

    device.auth()

    print("Broadlink: Learning mode... \nPlease press the matching button")
    device.enter_learning()

    while True:
        packet = device.check_data()
        if packet:
            print("\n\n Your packet is: \n\n {} \n\n"
                  .format(base64.b64encode(packet).decode('utf8')))
            if yesno("Do you want to learn next key (y/n): "):
                device.enter_learning()
                continue
            else:
                break
    return 0
