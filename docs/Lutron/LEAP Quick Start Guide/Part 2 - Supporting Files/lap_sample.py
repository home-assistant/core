# This sample code demonstrates the steps that are executed during the LAP certificate exchange process
# Use this in conjunction with the user guide to get started
# This file is not to be used in shipping software. LAP is an asynchronous protocol. This script is synchronous for simplicity of instruction.
# (c) Lutron Electronics Co. Inc. 2023. All rights reserved
#
import os, sys
import json
import socket
import ssl
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Step 1: Find the Lutron CA certs, your signed cert and your private key
#         Combine Lutron CA certs into a cert chain for Python
from definitions import *
print ("Look for certs")
if not (os.path.isfile(LAP_PRIVATE_KEY_FILE) and os.path.isfile(LAP_SIGNED_CSR_FILE) and os.path.isfile(LAP_LUTRON_ROOT_FILE) and os.path.isfile(LAP_LUTRON_INTERMEDIATE_FILE)):
    print(f"  Error: Create or download the required keys and certs: {LAP_PRIVATE_KEY_FILE}, {LAP_SIGNED_CSR_FILE}, {LAP_LUTRON_ROOT_FILE}, {LAP_LUTRON_INTERMEDIATE_FILE}")
    sys.exit()
with open(LAP_LUTRON_CHAIN_FILE, "w") as dst_file:
    with open(LAP_LUTRON_ROOT_FILE, "r") as src_file:
        for line in src_file.readlines():
            dst_file.write(line)
    with open(LAP_LUTRON_INTERMEDIATE_FILE, "r") as src_file:
        for line in src_file.readlines():
            dst_file.write(line)
print ("  Success")

# Step 2: Create the device specific private key and certificate signing request. These are specific to this device.
#
print ("Create a private key and CSR")
try:
    _LEAP_cert_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, DEVICE_COMMON_NAME)])
    _LEAP_private_key_object = rsa.generate_private_key (public_exponent=65537, key_size=2048, backend=default_backend())
    _LEAP_client_csr_object = x509.CertificateSigningRequestBuilder().subject_name(_LEAP_cert_subject).sign(_LEAP_private_key_object, hashes.SHA256(), default_backend())
except Exception as e:
    print (f"  Error: {e}")
    sys.exit()
print ("  Success")

# helper functions to write a JSON object to a socket and receive a JSON object from a socket
#
def _send_json (socket, json_msg):
    send_msg = (json.dumps(json_msg)+"\r\n").encode("ASCII")
    #print("Sent: " + f"{send_msg}")
    socket.sendall(send_msg)

def _recv_json (socket):
    recv_msg = socket.recv(5000)
    #print("Rcvd: " + recv_msg.decode("ASCII"))
    if len(recv_msg) == 0:
        return None
    else:
        return (json.loads(recv_msg.decode("ASCII")))

# Step 3: Establish a secure connection with the processor on the LAP port 8083
#         Setup a TLS connection, require certificate authentication, disable host name check, use contatenated CA file
print ("Establish a secure connection to Lutron Processor at " + LUTRON_PROC_ADDRESS + " using your LAP certs")
try:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode=ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=LAP_LUTRON_CHAIN_FILE)
    context.load_cert_chain(certfile=LAP_SIGNED_CSR_FILE, keyfile=LAP_PRIVATE_KEY_FILE)
    context.check_hostname=False
    sock = socket.create_connection((LUTRON_PROC_ADDRESS, 8083))
    ssock = context.wrap_socket(sock)
    sock.close()
except Exception as e:
    print (f"  Error: {e}")
    sys.exit()

_send_json(ssock,
    { 
        "Header": 
        { 
            "RequestType": "Ping", "ClientTag": "xyzzy" 
        } 
    }
)
recv_msg = _recv_json(ssock)
if recv_msg != None and recv_msg["Header"]["StatusCode"] == "204 No Content": # response is 200 OK for success
    print ("  Success")
else:
    if recv_msg == None:
        print ("  Error: processor closed the connection. Have you setup the processor with Lutron's tools?")
    else:
        print ("  Error: received an error response from the processor")
    sys.exit()

# Step 4: Check that the user has physical access to the device to authorize the LAP process
#         To demonstrate physical access the user must press the button on the device (location varies by device)
print("Waiting for you to prove physical access to the processor by pushing the button on the processor")
recv_msg = _recv_json(ssock)
if recv_msg != None and recv_msg["Header"]["StatusCode"] == "200 OK": # response is 200 OK for success
    print ("  Success: detected button press")
else:
    print ("  Error: received a error response from the processor")
    sys.exit()

# Step 5: Retrieve the device's CA cert
#         This will be used when integrating to this processor to validate the device you're connected to
print("Retrieve the processor's CA certificate")
_send_json(ssock,
    {
        "Header": {
            "RequestType": "Read",
            "Url": "/certificate/root",
            "ClientTag": "read-root",
        },  
    }
)
root_resp = _recv_json(ssock)
if recv_msg != None and recv_msg["Header"]["StatusCode"] == "200 OK": # response is 200 OK for success
    print ("  Success: Received")
else:
    print ("  Error: Received a error response from the processor")
    sys.exit()
_LEAP_lutron_proc_root_file_bytes = root_resp["Body"]["Certificate"]["Certificate"]

# Step 6: Send the Lutron processor the CSR created in step 5 and receive the certs you will need to connect to the processor on the integration port 8081
#         You will receive a signed CSR and a processor device specific CA certificate (not used)
#         You must provide a Display Name for your device otherwise the call will fail
#         The certs and key are then saved to files (defined in definitions.py) for use with openssl or the leap_sample.py script
print("Send the created CSR to the processor for signing")
_send_json(ssock,
    {
        "Header": {
            "RequestType": "Execute",
            "Url": "/pair",
            "ClientTag": "get-cert",
        },
        "Body": {
            "CommandType": "CSR",
            "Parameters": {
                "CSR": _LEAP_client_csr_object.public_bytes(serialization.Encoding.PEM).decode('ASCII'),
                "DisplayName": "XYZ",
                "DeviceUID": "000000000000"            },
        },
    }
)
recv_msg = _recv_json(ssock)
if recv_msg != None and recv_msg["Header"]["StatusCode"] == "200 OK": # response is 200 OK for success
    print ("  Success: Signed certificate and intermediate root certificate received and saved to file")
else:
    print ("  Error: Received a error response from the processor")
    sys.exit()
_LEAP_signed_csr_bytes = recv_msg["Body"]["SigningResult"]["Certificate"]
_LEAP_lutron_proc_intermediate_file_bytes = recv_msg["Body"]["SigningResult"]["RootCertificate"]
_LEAP_private_key_bytes = str(_LEAP_private_key_object.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()), 'ASCII')

with open(LEAP_PRIVATE_KEY_FILE, "w") as file:
    file.write(_LEAP_private_key_bytes)

with open(LEAP_SIGNED_CSR_FILE, "w") as file:
    file.write(_LEAP_signed_csr_bytes)

with open(LEAP_LUTRON_PROC_INTERMEDIATE_FILE, "w") as file:
    file.write(_LEAP_lutron_proc_intermediate_file_bytes)

with open(LEAP_LUTRON_PROC_ROOT_FILE, "w") as file:
    file.write(_LEAP_lutron_proc_root_file_bytes)

ssock.close()

print("Done")
print("  Run leap_sample.py to test your certs")