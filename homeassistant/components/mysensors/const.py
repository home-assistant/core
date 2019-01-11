"""MySensors constants."""
import homeassistant.helpers.config_validation as cv

ATTR_DEVICES = 'devices'

CONF_BAUD_RATE = 'baud_rate'
CONF_DEVICE = 'device'
CONF_GATEWAYS = 'gateways'
CONF_NODES = 'nodes'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_RETAIN = 'retain'
CONF_TCP_PORT = 'tcp_port'
CONF_TOPIC_IN_PREFIX = 'topic_in_prefix'
CONF_TOPIC_OUT_PREFIX = 'topic_out_prefix'
CONF_VERSION = 'version'

DOMAIN = 'mysensors'
MYSENSORS_GATEWAY_READY = 'mysensors_gateway_ready_{}'
MYSENSORS_GATEWAYS = 'mysensors_gateways'
PLATFORM = 'platform'
SCHEMA = 'schema'
CHILD_CALLBACK = 'mysensors_child_callback_{}_{}_{}_{}'
NODE_CALLBACK = 'mysensors_node_callback_{}_{}'
TYPE = 'type'
UPDATE_DELAY = 0.1

# MySensors const schemas
BINARY_SENSOR_SCHEMA = {PLATFORM: 'binary_sensor', TYPE: 'V_TRIPPED'}
CLIMATE_SCHEMA = {PLATFORM: 'climate', TYPE: 'V_HVAC_FLOW_STATE'}
LIGHT_DIMMER_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_DIMMER',
    SCHEMA: {'V_DIMMER': cv.string, 'V_LIGHT': cv.string}}
LIGHT_PERCENTAGE_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_PERCENTAGE',
    SCHEMA: {'V_PERCENTAGE': cv.string, 'V_STATUS': cv.string}}
LIGHT_RGB_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_RGB', SCHEMA: {
        'V_RGB': cv.string, 'V_STATUS': cv.string}}
LIGHT_RGBW_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_RGBW', SCHEMA: {
        'V_RGBW': cv.string, 'V_STATUS': cv.string}}
NOTIFY_SCHEMA = {PLATFORM: 'notify', TYPE: 'V_TEXT'}
DEVICE_TRACKER_SCHEMA = {PLATFORM: 'device_tracker', TYPE: 'V_POSITION'}
DUST_SCHEMA = [
    {PLATFORM: 'sensor', TYPE: 'V_DUST_LEVEL'},
    {PLATFORM: 'sensor', TYPE: 'V_LEVEL'}]
SWITCH_LIGHT_SCHEMA = {PLATFORM: 'switch', TYPE: 'V_LIGHT'}
SWITCH_STATUS_SCHEMA = {PLATFORM: 'switch', TYPE: 'V_STATUS'}
MYSENSORS_CONST_SCHEMA = {
    'S_DOOR': [BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_MOTION': [BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_SMOKE': [BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_SPRINKLER': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_STATUS'}],
    'S_WATER_LEAK': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_SOUND': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_LEVEL'},
        {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_VIBRATION': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_LEVEL'},
        {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_MOISTURE': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_LEVEL'},
        {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_HVAC': [CLIMATE_SCHEMA],
    'S_COVER': [
        {PLATFORM: 'cover', TYPE: 'V_DIMMER'},
        {PLATFORM: 'cover', TYPE: 'V_PERCENTAGE'},
        {PLATFORM: 'cover', TYPE: 'V_LIGHT'},
        {PLATFORM: 'cover', TYPE: 'V_STATUS'}],
    'S_DIMMER': [LIGHT_DIMMER_SCHEMA, LIGHT_PERCENTAGE_SCHEMA],
    'S_RGB_LIGHT': [LIGHT_RGB_SCHEMA],
    'S_RGBW_LIGHT': [LIGHT_RGBW_SCHEMA],
    'S_INFO': [NOTIFY_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_TEXT'}],
    'S_GPS': [
        DEVICE_TRACKER_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_POSITION'}],
    'S_TEMP': [{PLATFORM: 'sensor', TYPE: 'V_TEMP'}],
    'S_HUM': [{PLATFORM: 'sensor', TYPE: 'V_HUM'}],
    'S_BARO': [
        {PLATFORM: 'sensor', TYPE: 'V_PRESSURE'},
        {PLATFORM: 'sensor', TYPE: 'V_FORECAST'}],
    'S_WIND': [
        {PLATFORM: 'sensor', TYPE: 'V_WIND'},
        {PLATFORM: 'sensor', TYPE: 'V_GUST'},
        {PLATFORM: 'sensor', TYPE: 'V_DIRECTION'}],
    'S_RAIN': [
        {PLATFORM: 'sensor', TYPE: 'V_RAIN'},
        {PLATFORM: 'sensor', TYPE: 'V_RAINRATE'}],
    'S_UV': [{PLATFORM: 'sensor', TYPE: 'V_UV'}],
    'S_WEIGHT': [
        {PLATFORM: 'sensor', TYPE: 'V_WEIGHT'},
        {PLATFORM: 'sensor', TYPE: 'V_IMPEDANCE'}],
    'S_POWER': [
        {PLATFORM: 'sensor', TYPE: 'V_WATT'},
        {PLATFORM: 'sensor', TYPE: 'V_KWH'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR'},
        {PLATFORM: 'sensor', TYPE: 'V_VA'},
        {PLATFORM: 'sensor', TYPE: 'V_POWER_FACTOR'}],
    'S_DISTANCE': [{PLATFORM: 'sensor', TYPE: 'V_DISTANCE'}],
    'S_LIGHT_LEVEL': [
        {PLATFORM: 'sensor', TYPE: 'V_LIGHT_LEVEL'},
        {PLATFORM: 'sensor', TYPE: 'V_LEVEL'}],
    'S_IR': [
        {PLATFORM: 'sensor', TYPE: 'V_IR_RECEIVE'},
        {PLATFORM: 'switch', TYPE: 'V_IR_SEND',
         SCHEMA: {'V_IR_SEND': cv.string, 'V_LIGHT': cv.string}}],
    'S_WATER': [
        {PLATFORM: 'sensor', TYPE: 'V_FLOW'},
        {PLATFORM: 'sensor', TYPE: 'V_VOLUME'}],
    'S_CUSTOM': [
        {PLATFORM: 'sensor', TYPE: 'V_VAR1'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR2'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR3'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR4'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR5'},
        {PLATFORM: 'sensor', TYPE: 'V_CUSTOM'}],
    'S_SCENE_CONTROLLER': [
        {PLATFORM: 'sensor', TYPE: 'V_SCENE_ON'},
        {PLATFORM: 'sensor', TYPE: 'V_SCENE_OFF'}],
    'S_COLOR_SENSOR': [{PLATFORM: 'sensor', TYPE: 'V_RGB'}],
    'S_MULTIMETER': [
        {PLATFORM: 'sensor', TYPE: 'V_VOLTAGE'},
        {PLATFORM: 'sensor', TYPE: 'V_CURRENT'},
        {PLATFORM: 'sensor', TYPE: 'V_IMPEDANCE'}],
    'S_GAS': [
        {PLATFORM: 'sensor', TYPE: 'V_FLOW'},
        {PLATFORM: 'sensor', TYPE: 'V_VOLUME'}],
    'S_WATER_QUALITY': [
        {PLATFORM: 'sensor', TYPE: 'V_TEMP'},
        {PLATFORM: 'sensor', TYPE: 'V_PH'},
        {PLATFORM: 'sensor', TYPE: 'V_ORP'},
        {PLATFORM: 'sensor', TYPE: 'V_EC'},
        {PLATFORM: 'switch', TYPE: 'V_STATUS'}],
    'S_AIR_QUALITY': DUST_SCHEMA,
    'S_DUST': DUST_SCHEMA,
    'S_LIGHT': [SWITCH_LIGHT_SCHEMA],
    'S_BINARY': [SWITCH_STATUS_SCHEMA],
    'S_LOCK': [{PLATFORM: 'switch', TYPE: 'V_LOCK_STATUS'}],
}
