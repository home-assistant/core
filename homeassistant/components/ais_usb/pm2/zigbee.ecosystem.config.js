module.exports = {
  apps : [
    // Zigbee2MQTT
    {
      name          : 'zigbee',
      script        : '/data/data/pl.sviete.dom/files/home/zigbee2mqtt',
      error_file    : '/dev/null',
      out_file      : '/dev/null',
      restart_delay : 30000
    }
  ]
};
