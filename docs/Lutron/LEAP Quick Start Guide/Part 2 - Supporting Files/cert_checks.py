# This runs a few validations on your keys and certs which is valuable for debugging.
# This file is not to be used in shipping software. It does not run exhaustive security validations on your certs and keys.
# Run pip install pycryptodome for Crypto.PublicKey
# (c) Lutron Electronics Co. Inc. 2023. All rights reserved
#
import sys
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime
from Crypto.PublicKey import RSA

# Import the definitions and make sure all the certs you need exist
from definitions import *

# Step 1: Check validity of all certs
#
print ("Check if certs have expired")
certs = [LAP_SIGNED_CSR_FILE, LAP_LUTRON_ROOT_FILE, LAP_LUTRON_INTERMEDIATE_FILE, LEAP_SIGNED_CSR_FILE, LEAP_LUTRON_PROC_ROOT_FILE, LEAP_LUTRON_PROC_INTERMEDIATE_FILE]
now = datetime.now()
for certname in certs:
    try:
        with open(certname, "r") as cert_file:
            cert_bytes = cert_file.read()
            not_valid_after = x509.load_pem_x509_certificate(cert_bytes.encode()).not_valid_after
            not_valid_before = x509.load_pem_x509_certificate(cert_bytes.encode()).not_valid_before
            if now < not_valid_before or now > not_valid_after:
                print(f"  Fail: {certname} ({not_valid_before} to {not_valid_after})")
            else:
                print(f"  Success: {certname}")
    except Exception as e:
        print (f"  Error: {e}")

# Step 2: Check that the signed crs and private key correspond
#
print ("Check the private key generated the associated public key")
certs = [{LAP_PRIVATE_KEY_FILE, LAP_SIGNED_CSR_FILE}, {LEAP_PRIVATE_KEY_FILE, LEAP_SIGNED_CSR_FILE}]
for keyname, certname in certs:
    try:
        with open(certname, "r") as cert_file:
            cert_bytes = cert_file.read()
            certmodulus = RSA.import_key(cert_bytes).n
        with open(keyname, "r") as key_file:
            key_bytes = key_file.read()
            keymodulus = RSA.import_key(key_bytes).n
        if (certmodulus != keymodulus):
            print(f"  Fail: keypair {keyname} {certname}")
        else:
            print(f"  Success: keypair {keyname}, {certname}")
    except Exception as e:
        print (f"  Error: {e}")

# Step 3: Retrieve PROCESSOR_HOSTNAME from the LEAP_LUTRON_PROC_ROOT_FILE
#
print ("Retrieve the hostname from the processor's CA file")
try:
    with open(LEAP_LUTRON_PROC_ROOT_FILE, "r") as cert_file:
        cert_bytes = cert_file.read()
        PROCESSOR_HOSTNAME = x509.load_pem_x509_certificate(cert_bytes.encode()).issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
except Exception as e:
    print (f"  Error: {e}")
    sys.exit()
print(f"  Success: hostname is {PROCESSOR_HOSTNAME}")

