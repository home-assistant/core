# DVS Portal Dashboard Setup Guide

This guide will walk you through setting up the DVS Portal Dashboard in Home Assistant. The dashboard provides an overview of your parking reservations, balance, and other related information.

![Example HACS dashboard](./example-dashboard.png)

## Prerequisites

- Make sure you have installed the DVS Portal integration.
- Make sure you have HACS installed.

## Step 0: Install `auto-entities` Card through HACS

1. Navigate to **HACS** > **Frontend** in your Home Assistant dashboard.
2. Search for `auto-entities` in the search bar.
3. Click on it and then click **Install**.
4. After installation, add the following to your `ui-lovelace.yaml` or through the Lovelace UI:

```yaml
resources:
  - url: /hacsfiles/lovelace-auto-entities/auto-entities.js
    type: module
```

## Step 1: Create `input_text` for License Plate

Navigate to **Configuration** > **Helpers** in your Home Assistant dashboard.

1. Click the **ADD HELPER** button.
2. Choose **Text**.
3. Give it a name, for example, "DVS License Plate".
4. Set the Entity ID to `input_text.dvsportal_license_plate`.

## Step 2: Add Scripts

Add the following scripts to your `scripts.yaml` file.

```yaml
dvsportal_parkingreservation_endofday:
  sequence:
    - service: dvsportal.create_reservation
      data_template:
        entity_id: "{{ entity_id }}"
        license_plate_value: "{{ license_plate_value }}"
        date_from: "{{ (now() + timedelta(minutes=1)).isoformat() }}"
        date_until: "{{ now().replace(hour=23, minute=59, second=59).isoformat() }}"
create_and_clear_reservation:
  sequence:
    - service: dvsportal.create_reservation
      data_template:
        date_from: "{{ (now() + timedelta(minutes=1)).isoformat() }}"
        date_until: "{{ now().replace(hour=23, minute=59, second=59).isoformat() }}"
        license_plate_value: "{{ states('input_text.dvsportal_license_plate') }}"
    - service: input_text.set_value
      target:
        entity_id: input_text.dvsportal_license_plate
      data:
        value: none
```

Reload your scripts after adding these.

## Step 3: Create the Dashboard

1. Navigate to **Overview** > **Dashboards**.
2. Click on the **+** button to add a new dashboard.
3. Choose **Manual**.
4. Paste the following YAML code into the editor.

```yaml
type: vertical-stack
title: DVS Portal Dashboard
cards:
  - type: entities
    title: General Info
    entities:
      - entity: sensor.guest_parking_balance
      - entity: sensor.reservations
  - type: custom:auto-entities
    card:
      type: glance
      title: Cars without Reservations
    filter:
      include:
        - domain: sensor
          attributes:
            device_class: dvs_car_sensor
          state: not present
          options:
            tap_action:
              action: call-service
              service: script.dvsportal_parkingreservation_endofday
              service_data:
                entity_id: this.entity_id
  - type: custom:auto-entities
    card:
      type: glance
      title: Cars with Reservations
    filter:
      include:
        - domain: sensor
          attributes:
            device_class: dvs_car_sensor
          state: /^(reserved|present)$/
          options:
            tap_action:
              action: call-service
              service: dvsportal.end_reservation
              service_data:
                entity_id: this.entity_id
  - type: entities
    title: New car
    entities:
      - entity: input_text.dvsportal_license_plate
      - entity: script.create_and_clear_reservation
```

5. Save the dashboard.

You should now have a fully functional DVS Portal Dashboard!
