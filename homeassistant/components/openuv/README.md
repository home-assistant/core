# Steps to Display the Color-Coded UV Index Graph in the Lovelace Home Assistant Dashboard

## 1. Creating the UV Index Entity

In the `openuv` component of `sensor.py`, we created a new entity called `current_uv_index_with_graph`.  
This entity resides in the core of Home Assistant, and after its creation, it became available for use in the Lovelace dashboard.

---

## 2. Installing and Configuring HACS (Home Assistant Community Store)

### Step 1: Download and Install HACS
1. **Download the .zip file** containing the latest HACS release from [HACS GitHub Releases](https://github.com/hacs/integration/releases).
2. **Extract the downloaded file**.
3. Navigate to the `config` directory in your Home Assistant instance and check for the `custom_components` folder:
   - If it does not exist, create a folder named `custom_components` under `core/config/`.
4. **Copy the extracted HACS folder** into the `custom_components` folder:
   - Path: `core/config/custom_components/hacs`.
5. **Restart Home Assistant** to activate the HACS integration.

---

### Step 2: Adding HACS to Integrations
1. Open Home Assistant and go to **Settings > Devices & Services > Integrations**.
2. Click the **+ Add Integration** button in the bottom-right corner.
3. Search for **HACS** and click to add it.
4. During the setup process, HACS will prompt you to authenticate with GitHub:
   - Follow the instructions to complete the authentication.

Once HACS is installed, it can be used to install additional integrations or frontend elements, such as the **Mini-Graph-Card**  or **ApexCharts-Card** , which are essential for creating custom graphs.   

---

## 3. Installing and Configuring Graph Cards Using HACS

1. Navigate to **HACS** in the Home Assistant sidebar.
2. Use the search or browse feature to locate and install either:
   - **Mini-Graph-Card**, or  
   - **ApexCharts-Card** (recommended for advanced customization).   

These card integrations allows users in creating detailed and color-coded graph displays in the Lovelace dashboard.

---

## 4. Steps to Edit and Configure the UV Index Graph Code

### Step 1: Accessing the Dashboard Configuration
1. In the top-right corner of the screen, select the **Edit** button.
2. If this is your first time editing a dashboard, the **Edit dashboard** dialog will appear.
3. In the dialog, select the **three dots (⋮)** menu, then select **Take control** to enable editing.

---

### Step 2: Adding a Card for the Graph
1. Click the **+ Add Card** button at the bottom-right corner of the view.
2. In the card selection window, choose **Manual Card** or (at the bottom of the list).
3. A text editor will appear where you can input YAML code to configure the graph.

---

### Step 3: Writing the Graph Code for ApexCharts-Card

#### Using the ApexCharts-Card
Enter the following YAML code into the editor to create a detailed color-coded UV Index graph:

```yaml
type: custom:apexcharts-card
apex_config:
  chart:
    height: 100%
  dataLabels:
    background:
      enabled: false
    style:
      colors:
        - var(--primary-text-color)
graph_span: 24h
header:
  show: true
  show_states: true
  title: UV Index
experimental:
  color_threshold: true
yaxis:
  - id: left
    decimals: 1
    apex_config:
      forceNiceScale: true
series:
  - entity: sensor.openuv_current_uv_index_with_graph
    stroke_width: 2
    type: line
    color: rgb(192,192,192)
    yaxis_id: left
    float_precision: 0
    statistics:
      type: max
      period: 5minute
      align: middle
    show:
      datalabels: false
      extremas: false
      name_in_header: false
    color_threshold:
      - color: "#b200ff"
        value: 10.5
      - color: "#e45e65"
        value: 7.5
      - color: "#ff8000"
        value: 5.5
      - color: "#e0b400"
        value: 2.5
      - color: "#0da035"
        value: 0
    header_actions:
      tap_action:
        action: more-info
```

#### Using the Mini-Graph-Card

```yaml
type: custom:mini-graph-card
entities:
  - entity: sensor.openuv_current_uv_index_with_graph
    name: UV Index
name: UV Index
icon: mdi:weather-sunny
show:
  graph: bar
  extrema: true
  labels: true
  points: true
color_thresholds:
  - value: 0
    color: green
  - value: 2.1
    color: yellow
  - value: 5.1
    color: orange
  - value: 7.1
    color: red
  - value: 10.1
    color: purple
hours_to_show: 24
points_per_hour: 2
```

---

### Step 4: Save and Apply the Changes
After pasting the YAML code, click Save to add the graph to your dashboard.
The dashboard will now display the UV index graph with the color-coded thresholds applied.

---