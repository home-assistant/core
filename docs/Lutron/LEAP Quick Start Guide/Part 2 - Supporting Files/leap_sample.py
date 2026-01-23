# This sample code demonstrates the steps to connect to the processor with the certificates minted during the LAP process
# Use this in conjunction with the user guide to get started
# This file is not to be used in shipping software. LEAP is an asynchronous protocol. This script is synchronous for simplicity of instruction.
# (c) Lutron Electronics Co. Inc. 2023. All rights reserved
#
import os, sys
import json
import socket
import ssl
from cryptography import x509
from cryptography.x509.oid import NameOID

# Import the definitions and make sure all the certs you need exist
from definitions import *
print ("Look for certs")
if not (os.path.isfile(LEAP_PRIVATE_KEY_FILE) and os.path.isfile(LEAP_SIGNED_CSR_FILE)):
    print("  Error: You need to run lap_sample.py first to generate the keys needed for the API connection")
    sys.exit()
print ("  Success")

# helper functions to write a JSON object to a socket and receive a JSON object from a socket
#
def _send_json (socket, json_msg):
    send_msg = (json.dumps(json_msg)+"\r\n").encode("ASCII")
    #print("  Sent: " + f"{send_msg}")
    socket.sendall(send_msg)

def _recv_json (socket):
    recv_msg = socket.recv(5000)
    if len(recv_msg) == 0:
        return None
    else:
        #print("Rcvd: " + recv_msg.decode("ASCII"))
        return (json.loads(recv_msg.decode("ASCII")))

# Step 1: Generate the processor host name from the system type & mac address
#
print ("Determine the processor's hostname")
print(f"  Success: hostname is {LUTRON_PROC_HOSTNAME}")

# Step 2: Setup a connection with the LEAP API integration service (8081) using the certificates created above
#         The Lutron processor authenticates this client with the LEAP_SIGNED_CSR_FILE & LEAP_PRIVATE_KEY_FILE
#         The client authenticates the Lutron processor with the SERVER_HOSTNAME & LEAP_LUTRON_PROC_ROOT_FILE
#         Find the PROCESSOR_HOSTNAME in the certs
print ("Establish a password-less secure connection to Lutron Processor " + LUTRON_PROC_HOSTNAME + " at " + LUTRON_PROC_ADDRESS)
try:
    leap_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    leap_context.verify_mode=ssl.CERT_REQUIRED
    leap_context.load_verify_locations(cafile=LAP_LUTRON_ROOT_FILE)
    leap_context.load_cert_chain(certfile=LEAP_SIGNED_CSR_FILE, keyfile=LEAP_PRIVATE_KEY_FILE)
    leap_context.check_hostname=True
    sock = socket.create_connection((LUTRON_PROC_ADDRESS, 8081))
    ssock = leap_context.wrap_socket(sock, server_hostname=LUTRON_PROC_HOSTNAME)
    sock.close()
except Exception as e:
    print (f"  Error: {e}")
    sys.exit()
print ("  Success: Authenticated connection established")

# Step 3: Test that you have successfully signed in by reading the name of the root area of the system.
#
print ("Test the API by requesting the root area")
_send_json(ssock, 
    {
        "CommuniqueType": "ReadRequest",
        "Header": {
            "Url": "/area/rootarea"
        }
    }
)
recv_msg = _recv_json(ssock)
if recv_msg != None and recv_msg["Header"]["StatusCode"] == "200 OK": # response is 200 OK for success
    print (f"  Success. Found {recv_msg['Body']}")
else:
    print ("  Error: Received a error response from the processor")

ssock.close()
