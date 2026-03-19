# Threema Gateway Integration for Home Assistant

Send secure, end-to-end encrypted messages from Home Assistant to any Threema user using the Threema Gateway service.

## What is Threema Gateway?

[Threema Gateway](https://gateway.threema.ch/) allows you to send Threema messages programmatically. This integration enables Home Assistant to send notifications and alerts to Threema users.

**Common Use Cases:**
- Security alerts (door/window sensors)
- Temperature warnings
- System notifications
- Daily summaries

## Prerequisites

1. **Threema Gateway Account** - Sign up at [gateway.threema.ch](https://gateway.threema.ch/)
2. **Gateway Credentials** - You'll receive a Gateway ID (starts with `*`) and API Secret
3. **Message Credits** - Purchase credits to send messages

## Installation

### Step 1: Add Integration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Threema"**
4. Follow the setup wizard

### Step 2: Choose Setup Type

#### Option A: Create NEW Gateway ID (Recommended for E2E)
1. Select "Create NEW Gateway ID"
2. Home Assistant generates a key pair
3. **Copy the public key** shown on screen (hex part only, without `public:` prefix)
4. Go to https://gateway.threema.ch/ and create an **End-to-End Gateway ID**
5. **Paste the public key** during registration
6. Return to Home Assistant, enter your new Gateway ID and API Secret
7. Keys are automatically stored

#### Option B: Use EXISTING Gateway ID
1. Select "Use EXISTING Gateway ID"
2. Enter your Gateway ID and API Secret
3. **For E2E mode:** Also enter your private key (format: `private:abc123def456...`)
4. **Optionally:** Enter your public key (format: `public:def456abc123...`)
5. **For Basic mode:** Leave key fields empty

**Key Format Examples:**
```
Private Key: private:1a2b3c4d5e6f7890abcdef1234567890...
Public Key:  public:9876543210fedcba0987654321fedcba...
```

## Usage

### Service: `threema.send_message`

This is the primary way to send messages. Use it in automations, scripts, or Developer Tools > Services.

```yaml
service: threema.send_message
data:
  recipient: "ABCD1234"  # Threema ID of the recipient (8 characters)
  message: "Hello from Home Assistant!"
```

The integration automatically uses your configured gateway. If you have multiple gateways, specify which one:
```yaml
service: threema.send_message
data:
  config_entry_id: "01kh8feq7yz5qrj4d974sdg1w3"
  recipient: "ABCD1234"
  message: "Hello from Home Assistant!"
```

**How to find a Threema ID:**
- Open Threema app > Settings > My ID (8 characters, e.g., `ABCD1234`)

### Example Automation

Send an alert when a door opens:

```yaml
automation:
  - alias: "Front Door Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        from: "off"
        to: "on"
    action:
      - service: threema.send_message
        data:
          recipient: !secret my_threema_id
          message: >
            Front door opened at {{ now().strftime('%H:%M:%S') }}
```

**secrets.yaml:**
```yaml
my_threema_id: "YOURID12"
```

## Gateway Verification (QR Code)

When using E2E encryption (public key configured), a **QR code image entity** is created for your gateway device. This allows identity verification:

1. Go to **Settings** > **Devices & Services** > **Threema**
2. Click on your Gateway device
3. Find the **"Gateway QR Code"** image entity
4. Scan the QR code with the Threema app to verify the gateway's public key

The QR code encodes `3mid:<gateway_id>,<public_key_hex>` following the Threema verification format. This is only available when a public key is configured (E2E mode).

## Encryption Modes

### End-to-End (E2E) Mode
- Messages encrypted from Home Assistant to the recipient's device
- Maximum privacy - even Threema servers can't read them
- Requires private key setup

### Basic/Simple Mode
- Messages encrypted between Home Assistant and Threema servers
- Simpler setup, no key management needed
- Still secure for most use cases

## Key Management

**After key generation:**
- Keys are displayed once during setup - save them immediately
- Both keys are stored in Home Assistant's config entries
- Stored in: `/config/.storage/core.config_entries`

**Key Format:**
- Private keys start with `private:` followed by 64 hex characters
- Public keys start with `public:` followed by 64 hex characters

**Backup:** Save your keys securely (password manager or encrypted backup). If you lose your private key, you'll need to create a new Gateway ID.

## Reauthentication

If your credentials become invalid, Home Assistant will prompt you to re-enter your API Secret (and optionally your private key) through the reauthentication flow.

## Troubleshooting

### "Cannot Connect" Error
- Verify Gateway ID starts with `*` and is exactly 8 characters
- Check API Secret is correct
- Ensure you have remaining message credits
- Test credentials at gateway.threema.ch

### Messages Not Delivered
- Check you have credits: gateway.threema.ch > Account > Credits
- Verify recipient Threema ID is correct (8 characters)
- Check logs: Settings > System > Logs (search "threema")

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    homeassistant.components.threema: debug
```

## Security Best Practices

1. Store recipient IDs in `secrets.yaml`, not directly in automations
2. Backup your private key securely (if using E2E mode)
3. Monitor credit usage to detect abuse
4. Use E2E mode when possible for maximum privacy

## FAQ

**Q: Can I receive messages in Home Assistant?**
A: Not currently. This integration is send-only.

**Q: How much does it cost?**
A: A small amount per message. Check gateway.threema.ch for current pricing.

**Q: What's the message length limit?**
A: 3,500 characters.

**Q: Can I send images or files?**
A: Not yet. Text messages only in the current version.

## Roadmap

### Planned Features
- **Incoming messages via Gateway callbacks** — receive messages sent to your Gateway ID as HA events/triggers for automations (requires a publicly reachable URL, e.g. via Nabu Casa or Cloudflare tunnel)
- Image and file support
- Remaining credits sensor
- Rich media (video, audio, location sharing)
- Group messaging
- Message templates

## Support

- **Threema Gateway Docs:** https://gateway.threema.ch/en
- **HA Community:** https://community.home-assistant.io/
- **Issues:** Report via GitHub

## License

This integration uses the official Threema Gateway Python SDK.
- Home Assistant: Apache License 2.0
- Threema Gateway SDK: MIT License
