# This sample code captures the constants and filenames that are used by the sample files
# (c) Lutron Electronics Co. Inc. 2023. All rights reserved
#

# Step 1: Edit the lines below to add your processor's information. Use discovery_sample.py to find the 
#         a) Find serial number of the processor
#         b) Find the mac address of the processor (remove the ':')
#         c) Select the system type of the processor
#         d) Find the address (IP address or mDNS name) of the processor
#         Edit the DEVICE COMMON NAME to add the name of your device
LUTRON_PROC_SERIAL              = "0422150A"                    # set this to serial number of your processor
LUTRON_PROC_MAC                 = "6433db7a9428"                # set this to MAC address of your processor
LUTRON_PROC_SYSTEM_TYPE         = "homeworksqs"                 # set this to the system name {radioRa3, quantum (older athena procs), athena, myroom, homeworksqs}
LUTRON_PROC_ADDRESS             = "Lutron-0422150A.local."      # set this to the IP address or mDNS name of your processor
DEVICE_COMMON_NAME              = "ABC Corporation"             # set this to the CN of your company
LUTRON_PROC_HOSTNAME            = f"{LUTRON_PROC_SYSTEM_TYPE}-{LUTRON_PROC_MAC}-server" 

# Step 2: Collect the following certs into this folder and update the filenames below
#         LAP_PRIVATE_KEY_FILE          : the private key used to create the CSR
#         LAP_SIGNED_CSR_FILE           : the CSR signed by Lutron 
#         LAP_LUTRON_ROOT_FILE          : the Lutron root CA
#         LAP_LUTRON_INTERMEDIATE_FILE  : the Lutron integration intermediate CA
#         LAP_LUTRON_CHAIN_FILE         : concatenate LAP_LUTRON_ROOT_FILE and LAP_LUTRON_INTERMEDIATE_FILE 
LAP_PRIVATE_KEY_FILE            = "lap_private_key.pem"             # created by you, the developer
LAP_SIGNED_CSR_FILE             = "lap_signed_csr.pem"              # csr created by you, the developer, signed by Lutron
LAP_LUTRON_ROOT_FILE            = "lap_lutron_root.crt"             # downloaded from the Lutron dev portal
LAP_LUTRON_INTERMEDIATE_FILE    = "lap_lutron_intermediate.pem"     # downloaded from the Lutron dev portal
LAP_LUTRON_CHAIN_FILE           = "lap_lutron_chain.pem"            # concatenate LAP_LUTRON_ROOT_FILE and LAP_LUTRON_INTERMEDIATE_FILE for python

# Step 3: Define the filenames for the certs created by the LAP process. They are needed for a LEAP connection
#         LEAP_PRIVATE_KEY_FILE                 : the private key created by this software used to generate the CSR
#         LEAP_SIGNED_CSR_FILE                  : the csr signed by the processor (from the LAP response)
#         LEAP_LUTRON_PROC_ROOT_FILE            : the Lutron processor's CA (from the LAP response)
#         LEAP_LUTRON_PROC_INTERMEDIATE_FILE    : the Lutron integration intermediate CA (from the Lutron dev portal).
LEAP_PRIVATE_KEY_FILE               = "leap_private_key.pem"                # created by you, the developer, in software
LEAP_SIGNED_CSR_FILE                = "leap_signed_csr.pem"                 # received from the processor during the LAP process
LEAP_LUTRON_PROC_ROOT_FILE          = "leap_lutron_proc_root.pem"           # received from the processor during the LAP process
LEAP_LUTRON_PROC_INTERMEDIATE_FILE  = "leap_lutron_proc_intermediate.pem"   # received from the processor during the LAP process
