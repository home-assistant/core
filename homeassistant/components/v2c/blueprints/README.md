# V2C photovoltaic contracted power blueprint

The automation in `automation/contracted_power.yaml` updates the charger's
contracted power when its dynamic power mode changes. The charger uses the same
setting for the household and charger's contracted grid power in supported grid
modes and the target grid balance in PV-exclusive mode. Separate helpers keep
these values independent: a negative grid balance exports power, zero targets no
grid exchange, and a positive value allows grid import.

Copy the blueprint to
`config/blueprints/automation/v2c/contracted_power.yaml`, or import it from its
source URL once that URL is published.

1. Enable the photovoltaic installation option in the V2C integration.
2. Create two number helpers with ranges appropriate for your installation.
   Use W or kW as the unit, or leave the unit blank to use watts. The balance
   helper must allow negative values if exporting power is desired.
3. Create an automation from the blueprint and select the charger's **Dynamic
   power mode** entity and the two helpers. Create separate automations to set
   the contracted power helper for peak and valley tariffs if needed.
4. Run the new automation once to apply the active helper value immediately.
   It also applies when the mode or active helper changes, or Home Assistant
   starts.

The charger profile controls its own power in profile mode, which is not managed
by this automation.
