"""Module containing large string configurations for Home Assistant.

This module defines various large string constants used in the Home Assistant
dashboard and automation setups.
"""

dashboard_registry = r"""{
  "version": 1,
  "minor_version": 1,
  "key": "lovelace_dashboards",
  "data": {
    "items": [
      {
        "id": "help_ring_setup",
        "show_in_sidebar": false,
        "icon": "mdi:note-text",
        "title": "help_ring_setup",
        "require_admin": true,
        "mode": "storage",
        "url_path": "help-ring-setup"
      }
    ]
  }
}"""

mshls_help_ring_setup = r"""{
  "version": 1,
  "minor_version": 1,
  "key": "lovelace.help_ring_setup",
  "data": {
    "config": {
      "views": [
        {
          "title": "Ring Setup",
          "path": "ring-setup",
          "icon": "mdi:doorbell-video",
          "cards": [
            {
              "type": "vertical-stack",
              "cards": [
                {
                  "type": "markdown",
                  "content": "### Step 1 : Install & Start Remote API addon to get the Supervisor API key\n<a href=\"/hassio/addon/77f1785d_remote_api/info\" target=\"_blank\"\nrel=\"noopener noreferrer\">View Remote API</a>\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 2: Copy the API key from the log section  \n<a href=\"/hassio/addon/77f1785d_remote_api/logs\" target=\"_blank\" rel=\"noopener noreferrer\">View Logs</a>\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 3: Input the API key on the below input field\n"
                },
                {
                  "type": "entities",
                  "entities": [
                    "input_text.supervisor_api_key"
                  ]
                },
                {
                  "type": "markdown",
                  "content": "### Step 4: Install Mosquitto Broker & ring-mqtt Add-on\nClick the button below to install.\n"
                },
                {
                  "type": "button",
                  "name": "Install",
                  "icon": "mdi:cloud-upload",
                  "tap_action": {
                    "action": "call-service",
                    "service": "script.install_and_start_ring_mqtt_add_on"
                  }
                },
                {
                  "type": "conditional",
                  "conditions": [
                    {
                      "entity": "script.install_and_start_ring_mqtt_add_on",
                      "state_not": "off"
                    }
                  ],
                  "card": {
                    "type": "markdown",
                    "content": "⚠ **Installing Mosquitto Broker & ring-mqtt Add-on** ⚠  \n⏳ Please wait for **1 minute** until this message disappears.\n"
                  }
                },
                {
                  "type": "markdown",
                  "content": "### Step 5: Configure Ring MQTT Add-on\nAfter installation, open the add-on’s web UI to enter your Ring credentials and OTP.\n(If your OTP fails, use your authenticator app instead.)\n<a href=\"/hassio/addon/03cabcc9_ring_mqtt/config\" target=\"_blank\" rel=\"noopener noreferrer\">Open Ring MQTT UI</a>\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 6: Connect Home Assistant to Ring Cloud\nOnce logged in, check the add-on log for stream URL. \nSample: **\"stream_Source\":\"rtsp://rignev:pass2025@03cabcc9-ring-mqtt:8554/649a63ca6a1b_live\"**\nCopy the stream_Source url.\n<a href=\"/hassio/addon/03cabcc9_ring_mqtt/logs\" target=\"_blank\" rel=\"noopener noreferrer\">View Ring MQTT Logs</a>\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 7: Set Up Generic Camera in Home Assistant\nWhen configuring the generic camera, please make sure to:\n- **Select Stream Source URL** Input stream_Source url you copied in step 6.\n- **Select TCP** for the RTSP transport protocol. \n- **Authentication:** Choose **Basic**. \n  \n- **Frame Rate:** Set to **2**. \n  \n- **Verify SSL Certificate:** Tick this option. \n  \n- Leave allother settings empty.\n<a href=\"/config/integrations/integration/generic\" target=\"_blank\" rel=\"noopener noreferrer\">Generic Camera</a>\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 10: Edit Configuration.yaml\nModify the `configuration.yaml` file by replacing the `<Ring URL>` section with the Stream Source URL retrieved from the logs in step 6, formatted as:   `rtsp://rignev:<username>@<Ring URL>`.\nThis enables Home Assistant to store recordings. \n[Below is the part of the code in configuration.yaml you need to change]\n"
                },
                {
                  "type": "markdown",
                  "content": "```yaml\nshell_command:\n  ring_ffempg_record: ffmpeg -y -i \"<Ring URL>\" -t 10 -c copy /config/media/ring_doorbell/recording_$(date +\"%Y%m%d_%H%M%S\").mp4\n```\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 11: Restart Home Assistant\nApply the configuration changes by restarting Home Assistant.\n\n- Go to **Settings > System > Restart**\n\n<a href=\"/developer-tools/yaml\" target=\"_blank\"\nrel=\"noopener noreferrer\">Restart</a>\n\n- Wait for Home Assistant to fully reboot.\n"
                },
                {
                  "type": "markdown",
                  "content": "### Step 12: Create an Automation to Record Motion\n\nFollow these steps to set up an automation that will trigger recording when motion is detected:\n\n1. **Go to** `Settings > Automations & Scenes`.\n              \n2. **Click** on **Create Automation**.\n   <a href=\"/config/automation/edit/new\" target=\"_blank\"\n                        rel=\"noopener noreferrer\">Create Automation</a>\n3. **Choose** \"Start with an Empty Automation\".\n4. **Set the Trigger**:\n   - **Trigger Type**: Select **Device**.\n   - **Device**: Choose the motion sensor (Device ID: 313709d139b07d609f2235f76fa31f76).\n   - **Entity**: Select **binary_sensor.frontdoor_motion**.\n   - **Trigger**: Select **Motion**.\n   - **For**: Set to **1 second**.\n5. **Set the Actions**:\n   - **First Action**: Choose **Call Service**, then select **notify.mobile_app_bulentiphone** to send a mobile notification.\n     - **Message**: `Ring Detected Motion`\n     - **Title**: `Front Door Motion`\n   - **Second Action**: Choose **Create Persistent Notification** to display a message.\n     - **Message**: `Front Door Detected Motion v2`\n   - **Third Action**: Choose **Call Service**, then select **shell_command.ring_ffempg_record** to record the motion.\n6. **Save and Enable** the automation.\n\nOnce enabled, this automation will start recording whenever the motion sensor detects movement, triggering the appropriate services to record the event.\n"
                }
              ]
            }
          ]
        }
      ]
    }
  }
}"""
