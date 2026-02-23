# Flic Twist Protocol Specification

## Overview

This document describes the Bluetooth Low Energy (BLE) application-layer protocol used to communicate with a Flic Twist button. It covers advertising, GATT service discovery, pairing, session establishment, button and twist events, configuration, firmware updates, and miscellaneous operations.

All multi-byte integer fields are encoded in **little-endian** byte order unless otherwise stated. All packet structure definitions use the C `PACKED` attribute (`__attribute__((packed))`), meaning there is no padding between fields.

The Flic Twist does **not** use standard BLE encryption (SMP). All security is handled at the application layer using custom cryptographic protocols built on Ed25519, X25519, SHA-256, HMAC-SHA-256, and Chaskey-LTS MAC.

### Terminology

| Term | Definition |
|------|-----------|
| Host | The device connecting to the Flic Twist (e.g., a Flic Hub or smartphone). |
| Button / Device | The Flic Twist button itself. |
| Shall | Indicates a mandatory requirement. |
| Should | Indicates a recommended practice. |
| RFU | Reserved for Future Use. Shall be set to 0 by the sender and ignored by the receiver. |
| D360 | One full revolution of the twist ring, defined as `12 * 4096 = 49152` units. |

### Firmware Version

The firmware version is a monotonically increasing 32-bit unsigned integer. The current version at the time of writing is `2`.

## Advertising

The Flic Twist advertises in one of two modes: **private mode** (normal operation) or **public mode** (pairing mode). The device enters public mode when the user holds the button for approximately 6 seconds. Public mode times out automatically.

### Advertising Name

The advertising name is 8 characters long, constructed as follows:

| Position | Content | Description |
|----------|---------|-------------|
| 0 | `T` | Product identifier (Twist) |
| 1 | `0` | Fixed |
| 2-3 | `0`*x* | Firmware version as two decimal digits (e.g., `02` for version 2) |
| 4-7 | *xxxx* | Base64url-encoded lower 24 bits of the Bluetooth Device Address |

The base64url alphabet used is: `A-Z`, `a-z`, `0-9`, `-`, `_`.

### Private Mode Advertising

In private mode, the advertising data contains only flags:

| Offset | Length | Value | Description |
|--------|--------|-------|-------------|
| 0 | 1 | `0x02` | AD length |
| 1 | 1 | `0x01` | AD type: Flags |
| 2 | 1 | `0x06` | LE General Discoverable + BR/EDR Not Supported |

No scan response data is set in private mode.

### Private Mode Advertising Intervals

When advertising in private mode (e.g., after a button press while disconnected), the device cycles through three advertising periods:

| Period | Interval (RTC ticks) | Approx. Interval | Duration |
|--------|---------------------|-------------------|----------|
| 1 | 656 | ~20 ms | 10 seconds |
| 2 | 4997 | ~153 ms | 20 seconds |
| 3 | 33508 | ~1023 ms | 30 seconds |

After the last period, advertising stops unless per-pairing advertising settings override this behavior. The RTC runs at 32768 Hz.

### Public Mode Advertising

In public mode, the advertising data includes:

| Offset | Length | Value | Description |
|--------|--------|-------|-------------|
| 0 | 1 | `0x02` | AD length |
| 1 | 1 | `0x01` | AD type: Flags |
| 2 | 1 | `0x06` | LE General Discoverable + BR/EDR Not Supported |
| 3 | 1 | `0x11` | AD length (17) |
| 4 | 1 | `0x07` | AD type: Complete List of 128-bit Service UUIDs |
| 5-20 | 16 | *uuid* | Service UUID (see GATT Service section) |
| 21 | 1 | `0x09` | AD length (9) |
| 22 | 1 | `0x09` | AD type: Complete Local Name |
| 23-30 | 8 | *name* | Advertising name |

### Scan Response Data (Public Mode)

| Offset | Length | Value | Description |
|--------|--------|-------|-------------|
| 0 | 1 | `0x08` | AD length (8) |
| 1 | 1 | `0xFF` | AD type: Manufacturer Specific Data |
| 2-3 | 2 | `0x030F` | Company ID (Shortcut Labs, little-endian: `0x0F, 0x03`) |
| 4 | 1 | `0x02` | Product type: Flic Twist |
| 5-7 | 3 | *addr* | Upper 3 bytes of the Bluetooth Device Address (`address[3..5]`) |
| 8 | 1 | *flags* | Bit 0: address type (0=public, 1=static random). Bit 1: device is currently connected to another host. |

### Per-Pairing Advertising (After Lost Connection)

Each paired host can configure per-pairing advertising parameters (see SetAdvParametersRequest). When a BLE connection is lost (e.g., due to timeout or MIC failure), the device starts advertising using the configured parameters from all active pairings. The shortest configured interval is used. The first interval (`adv_intervals[0]`) is used during the first 5 seconds, then `adv_intervals[1]` is used for the remaining duration up to `timeout_seconds`.

## GATT Service

The Flic Twist exposes a single custom BLE GATT service for all protocol communication.

### Service UUID

```
00c90000-2cbd-4f2a-a725-5ccd960ffb7d
```

Stored in little-endian byte order: `{0x7d, 0xfb, 0x0f, 0x96, 0xcd, 0x5c, 0x25, 0xa7, 0x2a, 0x4f, 0xbd, 0x2c, 0x00, 0x00, 0xc9, 0x00}`.

### Characteristics

The service contains two characteristics:

| Name | UUID | Handle | Properties | Description |
|------|------|--------|------------|-------------|
| RX | `00c90001-2cbd-4f2a-a725-5ccd960ffb7d` | 16 (0x0010) | Write Without Response | Host writes packets to this characteristic. |
| TX | `00c90002-2cbd-4f2a-a725-5ccd960ffb7d` | 18 (0x0012) | Notify | Device sends packets via notifications on this characteristic. |

A Client Characteristic Configuration Descriptor (CCCD) is present at handle 19 (0x0013) to enable/disable notifications on the TX characteristic.

### MTU

The device declares a maximum ATT MTU of **140** bytes (via ATT Exchange MTU Response). The negotiated MTU is `min(client_mtu, 140)`. The default ATT MTU is 23 if no MTU exchange is performed.

The host-side implementation caps the effective ATT MTU at **130** bytes.

### GAP Service

The device also exposes a standard GAP service with a Device Name characteristic (handle 3) and an Appearance characteristic.

## Packet Structure

All protocol communication occurs through the RX and TX GATT characteristics. Each packet begins with a 1-byte **opcode** that identifies the packet type.

### Unsigned Packets

Packets exchanged before a session is established (during Full Verify and Quick Verify) are sent **unsigned** — the packet contains only the opcode and payload fields.

### Signed Packets

Once a session is established, all packets are signed using Chaskey-LTS MAC. A **5-byte signature** is appended to the end of every packet:

```
[opcode (1 byte)] [payload (variable)] [signature (5 bytes)]
```

The signature is computed over the opcode and payload bytes (i.e., everything except the signature itself), using the session key and a per-direction packet counter.

### Packet Opcodes

#### Host → Device (OpcodeToFlic)

| Value | Name |
|-------|------|
| 0 | `FULL_VERIFY_REQUEST_1` |
| 1 | `FULL_VERIFY_REQUEST_2_WITH_APP_TOKEN` |
| 2 | `FULL_VERIFY_REQUEST_2_WITHOUT_APP_TOKEN` |
| 3 | `FULL_VERIFY_ABORT_IND` |
| 4 | `TEST_IF_REALLY_UNPAIRED_REQUEST` |
| 5 | `QUICK_VERIFY_REQUEST` |
| 6 | `FORCE_BT_DISCONNECT_IND` |
| 7 | `GET_FIRMWARE_VERSION_REQUEST` |
| 8 | `DISCONNECT_VERIFIED_LINK_IND` |
| 9 | `SET_NAME_REQUEST` |
| 10 | `GET_NAME_REQUEST` |
| 11 | `START_API_TIMER_IND` |
| 12 | `INIT_BUTTON_EVENTS_REQUEST` |
| 13 | `ACK_BUTTON_EVENTS_IND` |
| 14 | `UPDATE_TWIST_POS_IND` |
| 15 | `START_FIRMWARE_UPDATE_REQUEST` |
| 16 | `FIRMWARE_UPDATE_DATA_IND` |
| 17 | `GET_BATTERY_LEVEL_REQUEST` |
| 18 | `FACTORY_RESET_REQUEST` |
| 19 | `GET_CURRENT_TIME_REQUEST` |
| 20 | `GET_DEVICE_ID_REQUEST` |
| 21 | `SET_ADV_PARAMETERS_REQUEST` |
| 22 | `GET_SENSORS_MIN_MAX_REQUEST` |
| 23 | `SET_LEDS_IND` |
| 24 | `FACTORY_CONFIG_REQUEST` |
| 25 | `CHANGE_CONFIG_REQUEST` |

#### Device → Host (OpcodeFromFlic)

| Value | Name |
|-------|------|
| 0 | `FULL_VERIFY_RESPONSE_1` |
| 1 | `FULL_VERIFY_RESPONSE_2` |
| 2 | `FULL_VERIFY_FAIL_RESPONSE` |
| 3 | `TEST_IF_REALLY_UNPAIRED_RESPONSE` |
| 4 | `GET_FIRMWARE_VERSION_RESPONSE` |
| 5 | `QUICK_VERIFY_NEGATIVE_RESPONSE` |
| 6 | `QUICK_VERIFY_RESPONSE` |
| 7 | `DISCONNECTED_VERIFIED_LINK_IND` |
| 8 | `INIT_BUTTON_EVENTS_RESPONSE` |
| 9 | `BUTTON_EVENT_NOTIFICATION` |
| 10 | `TWIST_EVENT_NOTIFICATION` |
| 11 | `API_TIMER_NOTIFICATION` |
| 12 | `GET_NAME_RESPONSE` |
| 13 | `SET_NAME_RESPONSE` |
| 14 | `START_FIRMWARE_UPDATE_RESPONSE` |
| 15 | `FIRMWARE_UPDATE_NOTIFICATION` |
| 16 | `GET_BATTERY_LEVEL_RESPONSE` |
| 17 | `FACTORY_RESET_RESPONSE` |
| 18 | `GET_CURRENT_TIME_RESPONSE` |
| 19 | `GET_DEVICE_ID_RESPONSE` |
| 20 | `SET_ADV_PARAMETERS_RESPONSE` |
| 21 | `GET_SENSORS_MIN_MAX_RESPONSE` |
| 22 | `FACTORY_CONFIG_RESPONSE` |
| 23 | `CHANGE_CONFIG_RESPONSE` |

## Session Cryptography

### Chaskey-LTS MAC

The Flic Twist uses **Chaskey-LTS** as its MAC (Message Authentication Code) algorithm. Chaskey-LTS is a lightweight, permutation-based MAC designed for 32-bit microcontrollers.

The implementation provides three operations:

- `chaskey_generate_subkeys(out[12], key[4])` — Expands a 128-bit key into 384 bits of subkey material (k, k1, k2).
- `chaskey_16_bytes(out[4], keys[12], data[4])` — Computes a 128-bit MAC over exactly 16 bytes of input data.
- `chaskey_with_dir_and_packet_counter(keys[12], dir, counter, data, len)` — Computes a MAC over arbitrary-length data, incorporating a direction flag and a 64-bit packet counter.

### Session Key Derivation

The session key is derived differently depending on whether the session was established via Full Verify or Quick Verify (see the respective sections).

### Packet Signing

Once a session is established, every packet is signed as follows:

1. Compute `signature = chaskey_with_dir_and_packet_counter(session_key, dir, counter, packet_data, packet_len)`.
   - `dir` = 1 for host→device, 0 for device→host.
   - `counter` is a 64-bit value that starts at 0 and increments by 1 for each packet sent in a given direction.
   - `packet_data` is the opcode byte followed by the payload (excluding the signature itself).
2. Append the first 5 bytes of the result to the packet.

The receiver verifies the signature by computing the expected MAC and comparing the first 5 bytes. If the signature does not match, the session shall be terminated with reason `DISCONNECT_LOGICAL_CONNECTION_REASON_INVALID_SIGNATURE`.

## Full Verification (New Pairing)

Full Verification is used when the host has no prior pairing with the device. The device must be in **public mode** for the pairing to succeed.

### Step 1: FullVerifyRequest1 (Host → Device)

The host sends a request to initiate the full verification process.

```c
struct FullVerifyRequest1 {
    // opcode = 0 (FULL_VERIFY_REQUEST_1)
    uint32_t tmp_id;        // Temporary identifier generated by the host
};
```

### Step 2: FullVerifyResponse1 (Device → Host)

The device responds with its factory certificate and key exchange material.

```c
struct FullVerifyResponse1 {
    uint8_t opcode;                 // 0 (FULL_VERIFY_RESPONSE_1)
    uint32_t tmp_id;                // Echoed from the request
    uint8_t signature[64];          // Ed25519 factory signature (see below)
    uint8_t address[6];             // Bluetooth Device Address
    uint8_t address_type;           // 0 = Public, 1 = Static Random
    uint8_t ecdh_public_key[32];    // Device's static X25519 public key
    uint8_t random_bytes[8];        // Device-generated random nonce
    uint8_t link_is_encrypted: 1;   // Always 0 (no BLE encryption)
    uint8_t is_in_public_mode: 1;   // 1 if the device is in pairing mode
    uint8_t has_bond_info: 1;       // Always 0
    uint8_t padding: 5;             // RFU
};
```

**Factory Signature**: The `signature` field contains an Ed25519 signature generated at the factory over the concatenation of `address` (6 bytes), `address_type` (1 byte), and `ecdh_public_key` (32 bytes) — 39 bytes total. The last 2 bits of `signature[32]` encode a certificate index `i` and are zeroed in the transmitted signature; the original value is used during key derivation.

**Host Verification of FullVerifyResponse1**:

1. Verify that `address` and `address_type` match the BLE connection's device address. Reject if they differ.
2. Verify the Ed25519 signature over the 39 bytes (`address || address_type || ecdh_public_key`) using the Shortcut Labs factory public key set. The verification function also extracts the certificate index `i` from the original `signature[32]`.
3. If the signature is invalid, abort with `GENUINE_CHECK_FAILED_SUBCODE_INVALID_CERTIFICATE`.

### Step 3: FullVerifyRequest2 (Host → Device)

After verifying the device's certificate, the host performs ECDH key exchange and sends a verifier.

```c
struct FullVerifyRequest2WithoutAppToken {
    // opcode = 2 (FULL_VERIFY_REQUEST_2_WITHOUT_APP_TOKEN)
    uint8_t ecdh_public_key[32];    // Host's ephemeral X25519 public key
    uint8_t random_bytes[8];        // Host-generated random nonce
    uint8_t signature_variant: 3;   // Signature algorithm variant
    uint8_t encryption_variant: 3;  // Encryption algorithm variant
    uint8_t must_validate_app_token: 1; // Whether the device must validate app credentials
    uint8_t padding: 1;             // RFU
    uint8_t verifier[16];           // HMAC-SHA-256 verifier (truncated to 16 bytes)
};
```

Alternatively, if the host provides app credentials:

```c
struct FullVerifyRequest2WithAppToken {
    // opcode = 1 (FULL_VERIFY_REQUEST_2_WITH_APP_TOKEN)
    uint8_t ecdh_public_key[32];    // Host's ephemeral X25519 public key
    uint8_t random_bytes[8];        // Host-generated random nonce
    uint8_t signature_variant: 3;   // Signature algorithm variant
    uint8_t encryption_variant: 3;  // Encryption algorithm variant
    uint8_t must_validate_app_token: 1; // Whether the device must validate app credentials
    uint8_t padding: 1;             // RFU
    uint8_t encrypted_app_token[16]; // Encrypted application token
    uint8_t verifier[16];           // HMAC-SHA-256 verifier (truncated to 16 bytes)
};
```

**Key Derivation (shared between host and device)**:

1. Compute the X25519 shared secret: `shared_secret = X25519(my_private_key, peer_public_key)`.
2. Extract the 2-bit certificate index `i` from `factory_signature[32] & 0x03`.
3. Derive the session master secret using SHA-256:
   ```
   master_secret = SHA-256(shared_secret || i || button_random_bytes || host_random_bytes || flags)
   ```
   Where `flags` is a single byte containing `signature_variant | (encryption_variant << 3) | (must_validate_app_token << 6)`.

4. Compute the verifier:
   - Without app token: `AT = HMAC-SHA-256(master_secret, "AT")`, verifier = first 16 bytes of `AT`.
   - With app token: `AT = HMAC-SHA-256(master_secret, "AT" || encrypted_app_token)`, verifier = first 16 bytes of `AT`.

5. Derive the session key: `SK = HMAC-SHA-256(master_secret, "SK")`. The first 16 bytes are expanded via `chaskey_generate_subkeys` to produce the 48-byte session key used for packet signing.

6. Derive the pairing key: `PK = HMAC-SHA-256(master_secret, "PK")`. The first 20 bytes are stored as the pairing data:
   - Bytes 0-3: `pairing_identifier` (uint32_t).
   - Bytes 4-19: `pairing_key` (128-bit Chaskey key).

**Device-side processing of FullVerifyRequest2**:

1. Compute the shared secret and master secret as described above.
2. Compute the expected verifier and compare with the received `verifier`. If they differ, respond with `FullVerifyFailResponse` with reason `FULL_VERIFY_FAIL_REASON_INVALID_VERIFIER`.
3. If the device is not in public mode, respond with reason `FULL_VERIFY_FAIL_REASON_NOT_IN_PUBLIC_MODE`.
4. Otherwise, derive SK and PK, store the pairing, and proceed.

### Step 4: FullVerifyResponse2 (Device → Host)

If the verifier is valid and the device is in public mode, the device responds with its identity and establishes the session. This packet is **signed** using the newly derived session key.

```c
struct FullVerifyResponse2 {
    uint8_t opcode;                     // 1 (FULL_VERIFY_RESPONSE_2)
    uint8_t app_credentials_match: 1;   // Whether app credentials matched
    uint8_t cares_about_app_credentials: 1; // Whether the device requires matching credentials
    uint8_t padding: 6;                 // RFU
    uint8_t button_uuid[16];            // Unique identifier for this button
    uint8_t name_len;                   // Length of the name in bytes
    char name[23];                      // User-assigned name (UTF-8, padded with NUL)
    uint32_t firmware_version;          // Current firmware version
    uint16_t battery_level;             // Raw ADC battery reading
    char serial_number[11];             // Serial number (e.g., "BA12-A00000")
    char color[16];                     // Device color (e.g., "white", "black")
};
```

**Battery level conversion**: The `battery_level` value is the measured voltage in millivolts. The device computes it from the 12-bit IADC reading (configured with the internal 1.21V reference and 0.5x analog gain, giving a 0-2420 mV measurement range) as `battery_level = raw_adc * 2420 / 4096`. No further conversion is needed to obtain millivolts.

Note: The host-side implementation (`flic_twist.cpp`) currently applies an additional `(battery_level * 3600 + 512) / 1024` conversion, which is shared with the Flic 2 codebase where the raw value has different ADC semantics. This produces incorrect millivolt values for the Flic Twist.

### FullVerifyFailResponse (Device → Host)

Sent if the full verification fails.

```c
struct FullVerifyFailResponse {
    uint8_t opcode;     // 2 (FULL_VERIFY_FAIL_RESPONSE)
    uint8_t reason;     // 0 = Invalid verifier, 1 = Not in public mode
};
```

### FullVerifyAbortInd (Host → Device)

The host can abort a pending full verification at any time by sending opcode 3 with no payload. The device resets the logical connection state.

## Quick Verification (Existing Pairing)

Quick Verification is used when the host already has a stored pairing with the device. It is faster than Full Verify and does not require the device to be in public mode.

### QuickVerifyRequest (Host → Device)

```c
struct QuickVerifyRequest {
    // opcode = 5 (QUICK_VERIFY_REQUEST)
    uint8_t random_client_bytes[7];     // Host-generated random nonce
    uint8_t signature_variant: 3;       // Signature algorithm variant
    uint8_t encryption_variant: 3;      // Encryption algorithm variant
    uint8_t padding: 2;                 // RFU
    uint32_t tmp_id;                    // Temporary identifier
    uint32_t pairing_identifier;        // Pairing ID from the stored pairing data
};
```

### QuickVerifyResponse (Device → Host)

If the device finds the `pairing_identifier` in its stored pairings, it responds with a signed response:

```c
struct QuickVerifyResponse {
    uint8_t opcode;                     // 6 (QUICK_VERIFY_RESPONSE)
    uint8_t random_button_bytes[8];     // Device-generated random nonce
    uint32_t tmp_id;                    // Echoed from the request
    uint8_t link_is_encrypted: 1;       // Always 0
    uint8_t has_bond_info: 1;           // Always 0
    uint8_t padding: 6;                 // RFU
};
// Followed by 5-byte Chaskey signature
```

**Session Key Derivation for Quick Verify**:

1. Construct a 16-byte seed: `seed = random_client_bytes[0..7] || random_button_bytes[0..8]` (where `random_client_bytes` is zero-extended to 8 bytes).
2. Expand the stored `pairing_key` (bytes 4-19 of the pairing data): `subkeys = chaskey_generate_subkeys(pairing_key)`.
3. Compute the session key seed: `session_key_seed = chaskey_16_bytes(subkeys, seed)`.
4. Expand the session key: `session_key = chaskey_generate_subkeys(session_key_seed)`.

The `QuickVerifyResponse` is the first packet signed with this session key (device→host direction, counter = 0). The host shall verify this signature to confirm the device holds the correct pairing key.

### QuickVerifyNegativeResponse (Device → Host)

If the device does not recognize the `pairing_identifier`, it responds with a negative response (unsigned):

```c
struct QuickVerifyNegativeResponse {
    uint8_t opcode;         // 5 (QUICK_VERIFY_NEGATIVE_RESPONSE)
    uint32_t tmp_id;        // Echoed from the request
};
```

Upon receiving this, the host should initiate a `TestIfReallyUnpaired` check to determine whether its pairing has been removed (e.g., due to factory reset).

## Unpaired Status Verification

When a Quick Verify returns a negative response, the host can verify whether its pairing has truly been removed from the device.

### TestIfReallyUnpairedRequest (Host → Device)

This request uses a fresh ECDH exchange to establish a temporary shared secret, then provides the stored pairing token for verification.

```c
struct TestIfReallyUnpairedRequest {
    // opcode = 4 (TEST_IF_REALLY_UNPAIRED_REQUEST)
    uint8_t ecdh_public_key[32];    // Host's ephemeral X25519 public key
    uint8_t random_bytes[8];        // Host-generated random nonce
    uint32_t pairing_identifier;    // Pairing ID from stored pairing data
    uint8_t pairing_token[16];      // Derived from stored pairing key
};
```

**Constructing the pairing_token (host side)**:

1. Perform ECDH and derive a master secret the same way as Full Verify Step 3 (using the FullVerifyResponse1 from the preceding exchange), but with the host's `random_bytes` being 8 bytes and `flags` set to 0.
2. Compute: `PT = HMAC-SHA-256(master_secret, "PT" || pairing_data)` where `pairing_data` is the full 20-byte stored pairing blob.
3. `pairing_token = PT[0..15]` (first 16 bytes).

### TestIfReallyUnpairedResponse (Device → Host)

```c
struct TestIfReallyUnpairedResponse {
    uint8_t opcode;         // 3 (TEST_IF_REALLY_UNPAIRED_RESPONSE)
    uint8_t result[16];     // HMAC-SHA-256 result (truncated to 16 bytes)
};
```

**Device-side processing**:

1. Derive the master secret using the same ECDH + SHA-256 procedure.
2. Look up the `pairing_identifier` in stored pairings.
3. If found, compute `PT = HMAC-SHA-256(master_secret, "PT" || pairing_identifier || pairing_key)` and verify the provided `pairing_token` against `PT[0..15]`.
   - If the token matches: respond with `result = HMAC-SHA-256(master_secret, "EX" || pairing_token)[0..15]`. This indicates the pairing **exists** on the device (contradicting the negative Quick Verify response — an unexpected state).
   - If the token does not match: respond with `result = HMAC-SHA-256(master_secret, "NE" || pairing_token)[0..15]`.
4. If the `pairing_identifier` is not found: respond with `result = HMAC-SHA-256(master_secret, "NE" || pairing_token)[0..15]`. This confirms the pairing has been removed.

**Host-side verification**:

1. Compute `NE = HMAC-SHA-256(master_secret, "NE" || pairing_token)[0..15]`.
2. If `result == NE`: the pairing has been removed from the device. The host should delete its stored pairing data and mark the button as unpaired.
3. Otherwise, compute `EX = HMAC-SHA-256(master_secret, "EX" || stored_pairing_data[0..15])[0..15]`.
4. If `result == EX`: the pairing still exists (unexpected state).
5. If neither matches: verification failed (`GENUINE_CHECK_FAILED_SUBCODE_INVALID_CALCULATED_SIGNATURE`).

## Session Establishment

After Full Verify or Quick Verify succeeds, a session is established. The host shall then send an `InitButtonEventsRequest` to configure the device and receive queued events.

### InitButtonEventsRequest (Host → Device)

This is the first signed packet the host sends after session establishment. It configures the 13 twist states and synchronizes the event counter.

```c
struct InitButtonEventsRequestTwistState {
    uint32_t led_mode: 6;           // LED animation mode (see LED Modes)
    uint32_t has_click: 1;          // Whether click events are enabled for this position
    uint32_t has_double_click: 1;   // Whether double-click events are enabled
    uint32_t extra_leds_after: 4;   // Number of extra adjacent LEDs to group
    uint32_t padding: 4;            // RFU
    uint32_t position: 16;          // Initial position within this twist state (0 to D360)
    uint8_t timeout_seconds;        // Seconds before reverting to twist mode 0 (255 = infinite)
};

struct Config {
    struct InitButtonEventsRequestTwistState twist_state[13];
};

struct InitButtonEventsRequest {
    // opcode = 12 (INIT_BUTTON_EVENTS_REQUEST)
    uint32_t event_count;           // Last acknowledged event count
    struct Config config;           // Twist state configuration
    uint32_t boot_id;               // Last known boot ID
    // + 5-byte signature
};

struct InitButtonEventsRequestV2 {
    // opcode = 12 (INIT_BUTTON_EVENTS_REQUEST)
    uint32_t event_count;           // Last acknowledged event count
    struct Config config;           // Twist state configuration
    uint32_t boot_id;               // Last known boot ID
    uint8_t api_version;            // API version (set to 2 for V2 features)
    // + 5-byte signature
};
```

The 13 twist states correspond to:
- Index 0: Default twist mode (no selector position)
- Indices 1-11: Selector positions (corresponding to the 12 LED positions on the ring, minus 1 since position 0 is the default mode)
- Index 12: Push-twist mode (twisting while the button is held down)

### InitButtonEventsResponse (Device → Host)

```c
struct InitButtonEventsResponseV2 {
    uint8_t opcode;                     // 8 (INIT_BUTTON_EVENTS_RESPONSE)
    uint64_t has_queued_events: 1;      // 1 if there are queued events to send
    uint64_t timestamp: 47;            // Current device RTC time (32768 Hz ticks)
    uint32_t event_count;               // Current event count on the device
    uint32_t boot_id;                   // Current boot ID
    uint8_t api_version;                // Device API version (2)
    // + 5-byte signature
};
```

**Event synchronization**: The device compares the received `boot_id` and `event_count` with its own state. If the boot IDs match, events already acknowledged by the host (as indicated by `event_count`) are skipped. If the boot IDs differ, all queued events are considered new.

If `has_queued_events` is 1, the device will immediately begin sending `ButtonEventNotification` packets for the queued events. After all queued events are sent with `was_queued_last` set on the final one, the host should consider initial event synchronization complete.

### API Version Negotiation

The `api_version` field in `InitButtonEventsRequestV2` and `InitButtonEventsResponseV2` enables feature negotiation:

- **API version 1** (or omitted): Button event notifications use the V1 format (`ButtonEventNotificationItem` — 7 bytes per event).
- **API version 2**: Button event notifications use the V2 format (`ButtonEventNotificationItemV2` — 8 bytes per event, includes `twist_mode_index`).

## Button Events

Button events are detected on the device and queued for delivery to connected hosts. The device supports a queue of up to **16** events.

### Event Types

| Value | Type | Description |
|-------|------|-------------|
| 0 | `BUTTON_UP` | The button was released. |
| 1 | `BUTTON_DOWN` | The button was pressed. |
| 2 | `SINGLE_CLICK_TIMEOUT` | The single-click detection window expired (no second press). |
| 3 | `BUTTON_HOLD` | The button has been held for the hold threshold. |

### Event Encoding

Each event is encoded as a 4-bit value:

| Bits | Field | Description |
|------|-------|-------------|
| 0-1 | `type` | Event type (0-3) |
| 2 | `second` / `quick` / `also_single_click_first` | Context-dependent flag (see below) |
| 3 | `dbl` | Double-click flag |

Flag semantics by event type:
- **BUTTON_DOWN**: Bit 2 (`second`) = 1 if this is the second press of a potential double-click (i.e., the previous press was less than 0.5 seconds ago and was not itself the second part of a double click).
- **BUTTON_UP**: Bit 2 (`quick`) = 1 if the button was held for less than 0.5 seconds. Bit 3 (`dbl`) = 1 if this release is the second part of a double click.
- **BUTTON_HOLD**: Bit 2 (`also_single_click_first`) = 1 if the hold occurred during what was the second press of a double-click, so the first press should be reinterpreted as a single click.
- **SINGLE_CLICK_TIMEOUT**: No additional flags.

### Event Detection Logic

- **Single click**: `BUTTON_DOWN` (quick=don't care) → `BUTTON_UP` (quick=1, dbl=0) → `SINGLE_CLICK_TIMEOUT`
- **Double click**: `BUTTON_DOWN` → `BUTTON_UP` (quick=1) → `BUTTON_DOWN` (second=1) → `BUTTON_UP` (dbl=1)
- **Hold**: `BUTTON_DOWN` → `BUTTON_HOLD` (after ~1 second) → `BUTTON_UP` (quick=0)
- **Click or hold**: Distinguish by checking the `quick` flag on `BUTTON_UP`.

The hold threshold and double-click detection window are both approximately **0.5 seconds** for the double-click window. The hold detection fires after approximately **1 second**.

### ButtonEventNotification (Device → Host)

```c
struct ButtonEventNotification {
    uint8_t opcode;                         // 9 (BUTTON_EVENT_NOTIFICATION)
    uint32_t press_counter;                 // Monotonically increasing event counter
    struct ButtonEventNotificationItem events[];  // One or more events
    // + 5-byte signature
};

struct ButtonEventNotificationItem {
    uint64_t timestamp: 48;     // RTC timestamp at 32768 Hz
    uint64_t event_encoded: 4;  // Encoded event (see Event Encoding)
    uint64_t was_queued: 1;     // 1 if this event occurred before the session was established
    uint64_t was_queued_last: 1; // 1 if this is the last queued event
    uint64_t padding: 2;        // RFU
};
```

### ButtonEventNotificationV2 (Device → Host, API v2)

```c
struct ButtonEventNotificationV2 {
    uint8_t opcode;                             // 9 (BUTTON_EVENT_NOTIFICATION)
    uint32_t press_counter;                     // Monotonically increasing event counter
    struct ButtonEventNotificationItemV2 events[];  // One or more events
    // + 5-byte signature
};

struct ButtonEventNotificationItemV2 {
    uint64_t timestamp: 48;         // RTC timestamp at 32768 Hz
    uint64_t event_encoded: 4;      // Encoded event (see Event Encoding)
    uint64_t was_queued: 1;         // 1 if this event occurred before the session was established
    uint64_t was_queued_last: 1;    // 1 if this is the last queued event
    uint64_t twist_mode_index: 4;   // Active twist mode when the event occurred (0-12)
    uint64_t padding: 6;            // RFU
};
```

Multiple events can be batched into a single notification packet. Up to 5 events can fit in a V1 notification within a typical MTU.

### AckButtonEventsInd (Host → Device)

The host acknowledges received events by sending the `press_counter` value of the last processed event:

```c
struct AckButtonEventsInd {
    // opcode = 13 (ACK_BUTTON_EVENTS_IND)
    uint32_t event_count;       // press_counter from the last processed event
    // + 5-byte signature
};
```

This allows the device to free queue space and avoid resending acknowledged events on reconnection.

### Event Counter Semantics

The `press_counter` follows this pattern per physical button interaction:
- `press_counter mod 4 == 1`: BUTTON_DOWN
- `press_counter mod 4 == 2`: BUTTON_HOLD
- `press_counter mod 4 == 3`: BUTTON_UP
- `press_counter mod 4 == 0`: SINGLE_CLICK_TIMEOUT

More precisely, `press_counter = press_count * 2 - 1` for down events and `press_counter = press_count * 2` for up/hold/timeout events, where `press_count` increments on each button down.

## Twist Events

Twist events are sent when the user rotates the twist ring on the Flic Twist.

### Position Model

The twist ring position is tracked as a 64-bit unsigned value that can increase or decrease without bounds (i.e., it is not wrapped). One full revolution corresponds to **D360 = 49152** units. The initial position when a session starts is defined as `INIT_TWIST_POS = 12 * 4096 << 40`, which places the starting point well above zero to accommodate negative rotations.

Each of the 13 twist states tracks:
- `twist_pos`: Current absolute position.
- `twist_min`: The minimum bound of the current position window.

The **bounded position** (the value exposed to the application) is `twist_pos - twist_min`, which ranges from 0 to D360.

### TwistEventNotification (Device → Host)

Sent when the twist ring is rotated, at a rate determined by the connection interval.

```c
struct TwistEventNotification {
    uint8_t opcode;                         // 10 (TWIST_EVENT_NOTIFICATION)
    uint8_t twist_mode_index: 4;            // Active twist mode (0=twist, 1-11=selector, 12=push-twist)
    uint8_t last_min_update_was_top: 1;     // Direction of last boundary clamp
    uint8_t last_hub_update_packet_too_old: 1; // Hub's position update was too stale
    uint8_t padding: 2;                     // RFU
    int total_delta: 24;                    // Signed delta from last sent position
    int min_delta: 24;                      // Signed delta from current position to bottom extent
    int max_delta: 24;                      // Signed delta from current position to top extent
    uint16_t last_known_hub_packet_counter; // Counter for position synchronization
    // + 5-byte signature
};
```

**Delta interpretation**:
- `total_delta`: The total change in position since the last TwistEventNotification was sent.
- `min_delta`: `current_position - bottom_position_since_last_update` (always ≤ 0 or 0 if no downward movement).
- `max_delta`: `current_position - top_position_since_last_update` (always ≥ 0 or 0 if no upward movement).

The min/max deltas allow the host to reconstruct the full range of motion between updates, which is important for accurate bounded position tracking.

### UpdateTwistPosInd (Host → Device)

The host can update the minimum bound (effectively changing the bounded position) for a specific twist mode:

```c
struct UpdateTwistPosInd {
    // opcode = 14 (UPDATE_TWIST_POS_IND)
    uint8_t twist_mode_index;                       // Which twist mode to update (0-12)
    int64_t new_min: 48;                            // New minimum value (signed, relative to INIT_TWIST_POS)
    uint32_t num_received_update_packets_from_twist; // Synchronization counter
    // + 5-byte signature
};
```

The `num_received_update_packets_from_twist` field is used for synchronization: the device maintains a history of recent twist updates and can replay position changes that occurred after the host's last known state, ensuring the minimum bound is applied correctly even with in-flight twist events.

### Position Synchronization Algorithm

When the device processes an `UpdateTwistPosInd`:

1. Determine how many twist event packets have been sent since the host's reference point: `pkt_cnt_diff = tx_update_packet_counter - num_received_update_packets_from_twist`.
2. If `pkt_cnt_diff > NUM_TWIST_HISTORY_ITEMS` (8), the host's data is too stale; set `last_hub_update_packet_too_old = true` in subsequent twist notifications.
3. Otherwise, replay the position changes from the history buffer to reconstruct the position at the host's reference point, then apply the `new_min` and replay forward to the current position, clamping the position within `[min, min + D360]`.

## Configuration

### ChangeConfigRequest (Host → Device)

Updates the twist state configuration after the initial `InitButtonEventsRequest`.

```c
struct ChangeConfigRequest {
    // opcode = 25 (CHANGE_CONFIG_REQUEST)
    struct Config config;       // New configuration (13 twist states)
    // + 5-byte signature
};
```

### ChangeConfigResponse (Device → Host)

```c
struct ChangeConfigResponse {
    uint8_t opcode;             // 23 (CHANGE_CONFIG_RESPONSE)
    // + 5-byte signature
};
```

When a new configuration is applied, the device resets the twist position tracking (update counters, selector timeout, and twist mode index revert to 0).

### LED Modes

The `led_mode` field in `InitButtonEventsRequestTwistState` controls the LED animation:

| Value | Name | Description |
|-------|------|-------------|
| 0 | `LedModeNone` | No LED activity configured |
| 1 | `LedModeFill` | Fill animation from current position |
| 2 | `LedModePoint` | Single point indicator |
| 3 | `LedModeSingle` | Reserved (selector indicator) |
| 4 | `LedModeFillUnfill` | Fill and unfill animation |
| 5 | `LedModePointEase` | Point with easing animation |
| 6 | `LedModeSpin` | Spinning animation |
| 7 | `LedModeSpin2` | Spinning animation variant 2 |
| 8 | `LedModeSpin3` | Spinning animation variant 3 |
| 9 | `LedModeSpin4` | Spinning animation variant 4 |
| 10 | `LedModeFlash` | Flashing animation |
| 11 | `LedModeFillFade` | Fill with fade animation |

Note: The device-side implementation restricts `led_mode` to values 0-3. Values above 3 are currently treated as 0 on the device.

### Twist State Grouping

The `extra_leds_after` field in `InitButtonEventsRequestTwistState` allows grouping adjacent selector positions so they share the same twist state. When `extra_leds_after = N`, the next N selector positions inherit the same LED mode, click settings, and position from this state. Grouping is only valid for indices 0-11 (not push-twist at index 12). If a grouped position already has its own `extra_leds_after > 0`, the grouping is rejected and `extra_leds_after` is reset to 0.

### Selector Timeout

When the twist ring is rotated to a selector position (indices 1-11), a timeout timer starts. If `timeout_seconds` is not 255 (infinite), the device reverts to twist mode 0 (default) after the specified number of seconds of inactivity. The timeout is reset on each twist event.

## Session Management

### DisconnectVerifiedLinkInd (Host → Device)

The host can explicitly terminate the logical session:

```c
// opcode = 8 (DISCONNECT_VERIFIED_LINK_IND)
// No payload, just opcode + 5-byte signature
```

### DisconnectedVerifiedLinkInd (Device → Host)

Sent by the device when the session is terminated:

```c
struct DisconnectedVerifiedLinkInd {
    uint8_t opcode;     // 7 (DISCONNECTED_VERIFIED_LINK_IND)
    uint8_t reason;     // Disconnect reason
    // + 5-byte signature
};
```

| Reason | Name | Description |
|--------|------|-------------|
| 0 | `INVALID_SIGNATURE` | A received packet had an incorrect signature. |
| 1 | `BY_USER` | The session was terminated by user action. |

### Auto-Disconnect

If no session is established within **40 seconds** of a BLE connection being created, the device terminates the BLE connection. Similarly, if a session is terminated while a BLE connection is still active, a 40-second timer starts; if no new session is established, the BLE connection is terminated.

### SetConnectionParametersInd

After the initial button events are received, the host typically requests BLE connection parameter updates. This is handled at the BLE L2CAP layer (Connection Parameter Update Request), not through the Flic protocol.

## Battery Level

### GetBatteryLevelRequest (Host → Device)

```c
// opcode = 17 (GET_BATTERY_LEVEL_REQUEST)
// No payload, just opcode + 5-byte signature
```

### GetBatteryLevelResponse (Device → Host)

```c
struct GetBatteryLevelResponse {
    uint8_t opcode;             // 16 (GET_BATTERY_LEVEL_RESPONSE)
    uint16_t battery_level;     // Raw ADC battery reading
    // + 5-byte signature
};
```

**Voltage conversion**: The `battery_level` value is already in millivolts. The device computes it from the minimum observed 12-bit IADC sample as:

```
battery_level = battery_min_adc * 2420 / 4096
```

The IADC is configured with the internal 1.21V reference and 0.5x analog gain (`iadcCfgReferenceInt1V2`, `iadcCfgAnalogGain0P5x`), giving an effective measurement range of 0 to 2420 mV. The `battery_min_adc` value tracks the minimum ADC reading observed since boot (since battery voltage sags under load, the minimum gives the most representative reading).

For example, `battery_min_adc = 3385` corresponds to `3385 * 2420 / 4096 ≈ 2000 mV`, which the device firmware considers a low-battery threshold.

Note: The host-side implementation (`flic_twist.cpp`) currently applies an additional `(battery_level * 3600 + 512) / 1024` conversion inherited from the Flic 2 codebase. This formula is designed for the Flic 2's nRF52 ADC (which sends a raw 10-bit reading with a 3.6V reference) and produces incorrect results when applied to the Twist's already-converted millivolt value.

The battery level can also be requested without an established session (unsigned request/response), though the response may not contain a valid reading in this case.

## Current Time

### GetCurrentTimeRequest (Host → Device)

```c
// opcode = 19 (GET_CURRENT_TIME_REQUEST)
// No payload, just opcode + 5-byte signature
```

### GetCurrentTimeResponse (Device → Host)

```c
struct GetCurrentTimeResponse {
    uint8_t opcode;         // 18 (GET_CURRENT_TIME_RESPONSE)
    uint64_t time: 56;      // Current RTC time in ticks
    // + 5-byte signature
};
```

The time is a 56-bit unsigned value representing the number of ticks since the device booted. The RTC runs at **32768 Hz** (one tick = ~30.5 microseconds).

## Name Management

The Flic Twist stores a user-assigned name (up to 23 bytes, UTF-8 encoded) with an associated timestamp for conflict resolution.

### GetNameRequest (Host → Device)

```c
// opcode = 10 (GET_NAME_REQUEST)
// No payload, just opcode + 5-byte signature
```

### GetNameResponse (Device → Host)

```c
struct GetNameResponse {
    uint8_t opcode;                 // 12 (GET_NAME_RESPONSE)
    uint64_t timestamp_utc_ms: 48;  // Timestamp when the name was last set (ms since epoch)
    char name[];                    // Variable-length UTF-8 name
    // + 5-byte signature
};
```

### SetNameRequest (Host → Device)

```c
struct SetNameRequest {
    // opcode = 9 (SET_NAME_REQUEST)
    uint64_t timestamp_utc_ms: 47;  // Timestamp of this name update (ms since epoch)
    uint64_t force_update: 1;       // If 1, override even if device has a newer timestamp
    char name[];                    // Variable-length UTF-8 name (max 23 bytes)
    // + 5-byte signature
};
```

### SetNameResponse (Device → Host)

```c
struct SetNameResponse {
    uint8_t opcode;                 // 13 (SET_NAME_RESPONSE)
    uint64_t timestamp_utc_ms: 48;  // Timestamp of the currently stored name
    char name[];                    // The currently stored name
    // + 5-byte signature
};
```

**Conflict resolution**: The device updates the name only if `force_update` is 1, or if `timestamp_utc_ms` in the request is greater than the currently stored timestamp. This allows multiple hosts to update the name without conflicts — the most recent update wins. The response always contains the name currently stored on the device after processing the request.

The name is stored in NVM3 at key `0x100`, along with the 48-bit timestamp.

## Advertising Parameters

### SetAdvParametersRequest (Host → Device)

Configures per-pairing advertising parameters that control how the device advertises after losing a BLE connection.

```c
struct SetAdvParametersRequest {
    // opcode = 21 (SET_ADV_PARAMETERS_REQUEST)
    bool is_active;                         // Enable/disable this pairing's advertising settings
    bool remove_other_pairings_adv_settings; // Clear all other pairings' advertising settings
    bool with_short_range;                  // Advertise on 1M PHY
    bool with_long_range;                   // Advertise on Coded PHY
    uint16_t adv_intervals[2];              // Advertising intervals in 0.625 ms units
    uint32_t timeout_seconds;               // How long to advertise after connection loss
    // + 5-byte signature
};
```

- `adv_intervals[0]`: Used during the first 5 seconds after connection loss.
- `adv_intervals[1]`: Used after the first 5 seconds, until `timeout_seconds` is reached.
- Valid interval range: 32-16384 (20 ms to 10.24 seconds).
- If neither `with_short_range` nor `with_long_range` is set, both are enabled by default.

The intervals are converted from 0.625 ms units to RTC ticks: `rtc_ticks = (interval_0625ms * 2048 + 99) / 100`.

### SetAdvParametersResponse (Device → Host)

```c
struct SetAdvParametersResponse {
    uint8_t opcode;     // 20 (SET_ADV_PARAMETERS_RESPONSE)
    // + 5-byte signature
};
```

## Firmware Updates

The Flic Twist supports over-the-air (OTA) firmware updates. The firmware binary is encrypted with AES-128-CTR, compressed with LZMA, and signed with Ed25519.

### Firmware Binary Format

The firmware binary distributed to hosts has the following layout:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 8 | `iv` — AES-128-CTR initialization vector (little-endian uint64) |
| 8 | 4 | `length_uncompressed_words` — Uncompressed firmware size in 32-bit words (little-endian uint32) |
| 12 | 64 | `signature` — Ed25519 signature (first 32 bytes = R, last 32 bytes = S) |
| 76 | variable | Compressed and encrypted firmware data |

The total binary size is 76 bytes of header plus the compressed data. The `length_compressed_bytes` sent to the device equals the total binary size minus 76 (i.e., only the compressed data portion).

### Firmware Fetching

The host library does not directly download firmware. Instead, after a session is established, a `FLIC_TWIST_EVENT_TYPE_CHECK_FIRMWARE_REQUEST` event is emitted to the application layer. This event contains:

- `current_version` — The device's current firmware version (obtained from `GetFirmwareVersionResponse`).
- `button_uuid` — The 16-byte UUID of the button (from factory data).

The application is expected to use these values to query an internet service for available firmware updates. The result is supplied back via `flic_twist_on_downloaded_firmware()` with one of three outcomes:

| Result | Meaning | Retry interval |
|--------|---------|----------------|
| `SUCCESS` | A new firmware binary was downloaded and is ready to send. | — (update starts immediately) |
| `ALREADY_LATEST` | No newer firmware is available. | 24 hours |
| `FAILED` | The firmware check failed (network error, etc.). | 2 hours |

The downloaded firmware binary (the full file including the 76-byte header) must remain valid in memory until the session terminates or a new check firmware request is emitted.

### Firmware Check Scheduling

The host schedules firmware checks as follows:

1. **30 seconds** after session establishment — the initial firmware version request and check is triggered.
2. **24 hours** after a successful check that found no update (`ALREADY_LATEST`).
3. **2 hours** after a failed firmware check (`FAILED`).
4. **10 minutes** after the device rejects the update with a negative `start_pos` (invalid parameters or device busy).
5. **24 hours** after a signature verification failure on the device.

A persistent `next_firmware_check_timestamp_utc_ms` field is stored per button so that firmware checks survive session reconnects.

### GetFirmwareVersionRequest (Host → Device)

```c
// opcode = 7 (GET_FIRMWARE_VERSION_REQUEST)
// No payload (opcode only, may or may not have signature depending on session state)
```

This request can be sent both with and without an established session. Without a session, the response is unsigned.

### GetFirmwareVersionResponse (Device → Host)

```c
struct GetFirmwareVersionResponse {
    uint8_t opcode;             // 4 (GET_FIRMWARE_VERSION_RESPONSE)
    uint32_t version;           // Current firmware version
    // + 5-byte signature (if session is established)
};
```

### StartFirmwareUpdateRequest (Host → Device)

Initiates a firmware update transfer. The host parses the 76-byte firmware binary header and sends the fields individually:

```c
struct StartFirmwareUpdateRequest {
    // opcode = 15 (START_FIRMWARE_UPDATE_REQUEST)
    uint32_t length_compressed_bytes;   // Size of compressed data (total_binary_size - 76)
    uint64_t iv;                        // AES-128-CTR initialization vector (from binary offset 0)
    uint32_t length_uncompressed_words; // Uncompressed size in 32-bit words (from binary offset 8)
    uint8_t signature[64];              // Ed25519 signature (from binary offset 12)
    uint16_t status_interval;           // Send progress notification every N data packets (typically 2)
    // + 5-byte signature
};
```

The `status_interval` field must be at least 1. Setting it to 2 means the device sends a progress notification after every 2 data packets received.

### StartFirmwareUpdateResponse (Device → Host)

```c
struct StartFirmwareUpdateResponse {
    uint8_t opcode;         // 14 (START_FIRMWARE_UPDATE_RESPONSE)
    int32_t start_pos;      // Byte offset to resume from, or negative on error
    // + 5-byte signature
};
```

| `start_pos` value | Meaning |
|-------------------|---------|
| `0` | New firmware update started from the beginning. |
| `> 0` | Resuming a previously interrupted update. The device already has data up to this byte offset; the host should continue sending from here. Resume is possible when the `iv`, `length_compressed_bytes`, `length_uncompressed_words`, and `signature` all match the previous update attempt. |
| `-1` | Invalid parameters (firmware too large, compressed size too small, uncompressed size too small, or `status_interval` is 0). |
| `-2` | Device is busy (a different firmware update is already in progress). |
| `-3` | A firmware update has already completed and is pending application on next reboot. |

### FirmwareUpdateDataInd (Host → Device)

```c
struct FirmwareUpdateDataInd {
    // opcode = 16 (FIRMWARE_UPDATE_DATA_IND)
    uint8_t data[];         // Firmware data chunk (compressed+encrypted bytes from binary offset 76+)
    // + 5-byte signature
};
```

The host sends the compressed data (starting at offset 76 in the firmware binary) in sequential chunks.

**Flow control**: The host may have up to **480 bytes** in flight (sent but not yet acknowledged by a progress notification). Each data packet should contain up to **120 bytes** of payload. This means at most 4 packets can be in flight simultaneously. The host must not send more data until a `FirmwareUpdateNotification` advances the acknowledged position enough to allow it.

### FirmwareUpdateNotification (Device → Host)

```c
struct FirmwareUpdateNotification {
    uint8_t opcode;     // 15 (FIRMWARE_UPDATE_NOTIFICATION)
    int32_t pos;        // Current acknowledged byte position, or status code
    // + 5-byte signature
};
```

| `pos` value | Meaning |
|-------------|---------|
| `> 0` (intermediate) | The device has received and processed data up to this byte position. The host should update its acknowledged position and may send more data packets. |
| `== length_compressed_bytes` | The firmware update is **complete** and the signature has been verified. The host should send a `ForceBtDisconnectInd` with `restart_adv = true` to trigger the device reboot. |
| `== 0` | **Invalid firmware signature**. The Ed25519 signature verification failed after all data was received. The update is aborted. |

Progress notifications are sent every `status_interval` data packets during the transfer. The final completion or failure notification is sent once all data has been received and verified, regardless of `status_interval`.

### Device-Side Processing

On the device, firmware data is processed through a 128-byte write buffer:

1. **Buffering**: Incoming data chunks are accumulated in a 128-byte aligned buffer.
2. **SHA-512 hashing**: Each full buffer (or the final partial buffer) is fed into an incremental SHA-512 hash: `SHA-512(signature_R || public_key || iv || length_uncompressed_words || compressed_data)`.
3. **AES-128-CTR decryption**: The buffer is decrypted in-place using AES-128-CTR with a hardcoded device key and the provided IV. The counter increments per 16-byte block.
4. **Flash writing**: The decrypted data is written to flash storage in the area between the current application end and the NVM3 storage region. Flash pages are erased on demand before writing.
5. **Signature verification**: After all data is received, the SHA-512 hash is finalized to produce `hram`, and the Ed25519 signature is verified: `ed25519_verify_hram(public_key, signature, hram)`.
6. **Header commit**: If the signature is valid, a flash header is written with a magic value (`{0x467a97dc, 0xecc76d98, 0x78c05f5b, 0x9c44232f}`), the compressed length, uncompressed length, and commit markers. The bootloader uses this header to decompress and install the firmware on next boot.

### Update Completion

After the host receives a completion notification (`pos == length_compressed_bytes`):

1. The host sends `ForceBtDisconnectInd` with `restart_adv = true`.
2. The device terminates the BLE connection and sets a retention RAM flag to restart advertising after reboot.
3. On disconnect, the device reboots. The bootloader detects the committed firmware header, decompresses the LZMA data, writes the new application image, and boots into the updated firmware.
4. The device begins advertising again. The host reconnects, re-authenticates, and the new firmware version is reported via `GetFirmwareVersionResponse`.

### Cancellation

A firmware update can be cancelled by disconnecting the session (`DisconnectVerifiedLinkInd`) or the BLE link. If the update has not yet completed (signature not verified), the device resets its firmware update state. If the update has already completed (header committed to flash), the cancellation is ignored and the new firmware will be applied on next reboot regardless.

## Factory Reset

### FactoryResetRequest (Host → Device)

```c
// opcode = 18 (FACTORY_RESET_REQUEST)
// No payload, just opcode + 5-byte signature
```

### FactoryResetResponse (Device → Host)

```c
struct FactoryResetResponse {
    uint8_t opcode;     // 17 (FACTORY_RESET_RESPONSE)
    // + 5-byte signature
};
```

After sending the response, the device writes a factory reset marker to NVM3 and sets a retention RAM flag. On the next reboot (or disconnect), all stored pairings and user data are erased.

The user can also trigger a factory reset by holding the button for approximately 6 seconds while disconnected (entering public mode), which has separate handling.

## Miscellaneous

### GetDeviceIdRequest / Response

```c
// Request: opcode = 20 (GET_DEVICE_ID_REQUEST)
// No payload, just opcode + 5-byte signature

struct GetDeviceIdResponse {
    uint8_t opcode;             // 19 (GET_DEVICE_ID_RESPONSE)
    uint8_t device_id[8];       // Unique 64-bit device identifier
    // + 5-byte signature
};
```

### GetSensorsMinMaxRequest / Response

Returns the minimum and maximum ADC readings observed for the two hall-effect twist sensors since boot.

```c
// Request: opcode = 22 (GET_SENSORS_MIN_MAX_REQUEST)
// No payload, just opcode + 5-byte signature

struct GetSensorsMinMaxResponse {
    uint8_t opcode;                 // 21 (GET_SENSORS_MIN_MAX_RESPONSE)
    uint64_t sensor1_min: 12;       // Minimum reading from hall sensor 1
    uint64_t sensor1_max: 12;       // Maximum reading from hall sensor 1
    uint64_t sensor2_min: 12;       // Minimum reading from hall sensor 2
    uint64_t sensor2_max: 12;       // Maximum reading from hall sensor 2
    // + 5-byte signature
};
```

### SetLedsInd (Host → Device)

Enables or disables the LED animation override.

```c
struct SetLedsInd {
    // opcode = 23 (SET_LEDS_IND)
    bool enable;        // true to enable LED override
    // + 5-byte signature
};
```

### FactoryConfigRequest / Response

Sets the device color in factory flash (one-time programmable area).

```c
struct FactoryConfigRequest {
    // opcode = 24 (FACTORY_CONFIG_REQUEST)
    char color[16];     // Color string (e.g., "white", "black")
    // + 5-byte signature
};

struct FactoryConfigResponse {
    uint8_t opcode;     // 22 (FACTORY_CONFIG_RESPONSE)
    uint8_t result;     // 0 = success, non-zero = error
    // + 5-byte signature
};
```

The color is written to flash at address `0x7E0C0` (within the factory info region). This operation can only succeed if the target flash area is in an erased state (all `0xFF`).

### ApiTimerInd / Notification

Allows the host to start a timer on the device that fires a notification when it expires.

```c
struct ApiTimerInd {
    // opcode = 11 (START_API_TIMER_IND)
    uint32_t timeout;       // Timeout in RTC ticks (32768 Hz), 0 clears the timer
    uint32_t message;       // Opaque value echoed in the notification
    // + 5-byte signature
};

struct ApiTimerNotification {
    uint8_t opcode;         // 11 (API_TIMER_NOTIFICATION)
    uint32_t message;       // Echoed from the ApiTimerInd
    // + 5-byte signature
};
```

## Connection-less Packets

### ForceBtDisconnectInd (Host → Device)

Forces the device to terminate the BLE connection.

```c
struct ForceBtDisconnectInd {
    // opcode = 6 (FORCE_BT_DISCONNECT_IND)
    bool restart_adv;       // If true, restart advertising after disconnect
    // + 5-byte signature
};
```

This is typically used after a firmware update completes or when the host wants the device to reboot. The disconnect reason sent to the BLE controller is `0x13` (Remote User Terminated Connection).

If `restart_adv` is true and a firmware update was completed, the device sets a retention RAM flag so that advertising resumes after the reboot.

## Storage & Factory Data

### NVM3 Storage Keys

The device uses Silicon Labs NVM3 (Non-Volatile Memory Manager) for persistent storage:

| Key Range | Content |
|-----------|---------|
| `0x00` - `0x1F` | Pairing data (one entry per pairing, up to 32) |
| `0x100` | User-assigned name (8-byte timestamp + up to 23 bytes of name) |
| `0xFFFF` | Factory reset pending marker |

Each pairing entry is 28 bytes:
- `uint64_t seq_num` (8 bytes) — monotonically increasing sequence number for LRU eviction.
- `uint32_t id` (4 bytes) — pairing identifier.
- `uint32_t key[4]` (16 bytes) — 128-bit Chaskey pairing key.

When the maximum of 32 pairings is reached, the pairing with the lowest `seq_num` is evicted.

### Factory Data (Flash)

Factory-programmed data is stored at flash address **`0x7E000`** in the following layout:

```c
struct FactoryInfo {
    uint8_t random_bytes[32];           // Factory-generated random data
    uint8_t ecdh_public_key[32];        // X25519 public key
    uint8_t ecdh_private_key[32];       // X25519 private key
    uint8_t factory_signature[64];      // Ed25519 signature over (address || address_type || public_key)
    uint8_t button_uuid[16];            // Unique button UUID
    char serial_number[12];             // Serial number (NUL-terminated)
    uint8_t padding[4];                 // Unused
    char color[16];                     // Device color (at offset 0xC0 from start)
};
```

Total size: 208 bytes. The `color` field is at address `0x7E0C0`.

The Bluetooth Device Address is read from the EFR32's device information page (`DEVINFO->EUI48L`), not from the factory info struct.

## Appendix: Opcode Summary Table

### Host → Device

| Opcode | Name | Signed | Has Payload |
|--------|------|--------|-------------|
| 0 | FullVerifyRequest1 | No | Yes |
| 1 | FullVerifyRequest2WithAppToken | No | Yes |
| 2 | FullVerifyRequest2WithoutAppToken | No | Yes |
| 3 | FullVerifyAbortInd | No | No |
| 4 | TestIfReallyUnpairedRequest | No | Yes |
| 5 | QuickVerifyRequest | No | Yes |
| 6 | ForceBtDisconnectInd | Yes | Yes |
| 7 | GetFirmwareVersionRequest | Both | No |
| 8 | DisconnectVerifiedLinkInd | Yes | No |
| 9 | SetNameRequest | Yes | Yes |
| 10 | GetNameRequest | Yes | No |
| 11 | StartApiTimerInd | Yes | Yes |
| 12 | InitButtonEventsRequest | Yes | Yes |
| 13 | AckButtonEventsInd | Yes | Yes |
| 14 | UpdateTwistPosInd | Yes | Yes |
| 15 | StartFirmwareUpdateRequest | Yes | Yes |
| 16 | FirmwareUpdateDataInd | Yes | Yes |
| 17 | GetBatteryLevelRequest | Both | No |
| 18 | FactoryResetRequest | Yes | No |
| 19 | GetCurrentTimeRequest | Yes | No |
| 20 | GetDeviceIdRequest | Yes | No |
| 21 | SetAdvParametersRequest | Yes | Yes |
| 22 | GetSensorsMinMaxRequest | Yes | No |
| 23 | SetLedsInd | Yes | Yes |
| 24 | FactoryConfigRequest | Yes | Yes |
| 25 | ChangeConfigRequest | Yes | Yes |

### Device → Host

| Opcode | Name | Signed | Has Payload |
|--------|------|--------|-------------|
| 0 | FullVerifyResponse1 | No | Yes |
| 1 | FullVerifyResponse2 | Yes | Yes |
| 2 | FullVerifyFailResponse | No | Yes |
| 3 | TestIfReallyUnpairedResponse | No | Yes |
| 4 | GetFirmwareVersionResponse | Both | Yes |
| 5 | QuickVerifyNegativeResponse | No | Yes |
| 6 | QuickVerifyResponse | Yes | Yes |
| 7 | DisconnectedVerifiedLinkInd | Yes | Yes |
| 8 | InitButtonEventsResponse | Yes | Yes |
| 9 | ButtonEventNotification | Yes | Yes |
| 10 | TwistEventNotification | Yes | Yes |
| 11 | ApiTimerNotification | Yes | Yes |
| 12 | GetNameResponse | Yes | Yes |
| 13 | SetNameResponse | Yes | Yes |
| 14 | StartFirmwareUpdateResponse | Yes | Yes |
| 15 | FirmwareUpdateNotification | Yes | Yes |
| 16 | GetBatteryLevelResponse | Both | Yes |
| 17 | FactoryResetResponse | Yes | Yes |
| 18 | GetCurrentTimeResponse | Yes | Yes |
| 19 | GetDeviceIdResponse | Yes | Yes |
| 20 | SetAdvParametersResponse | Yes | Yes |
| 21 | GetSensorsMinMaxResponse | Yes | Yes |
| 22 | FactoryConfigResponse | Yes | Yes |
| 23 | ChangeConfigResponse | Yes | Yes |

"Both" in the Signed column indicates the packet can be sent either signed (during an established session) or unsigned (outside a session), with differing behavior.
