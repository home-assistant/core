import socket
import sys
import time
# Create socket for server
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.sendto("<ALL;DEVICE;ID;GET>".encode('utf-8'), ("HASS IP BUT WITH  .255 at the end (example 10.0.32.255)", 31415))
print("Waiting for DATA...")
# close the socket
s.close()
# new socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
config= (ADD HASS IP, 31415)
s.bind(config)
discover = []
print("Socket loaded \n")
t_end = time.time() + 5
time.sleep(1)
s.settimeout(0.05)
a=""
while time.time() < t_end:
    try:
        data, address = s.recvfrom(4096)
        c=data.decode('utf-8')
        discover.append(c)
        
    except socket.timeout:
        if a == data.decode('utf-8'):
            b="Not Found"
        else:
            b=data.decode('utf-8')
            a=data.decode('utf-8')
        print("Scan[" + b + "]")
    finally:
        b=""
print("Discovery complete: " + str(len(discover)) + " device/devices found.")
for x in range(len(discover)):
    print(discover[x])
    x+=1
