"""Constants for the rpi_gpio_pwm integration."""

DOMAIN = "rpi_gpio_pwm"

CONF_DRIVER = "driver"
CONF_FREQUENCY = "frequency"

CONF_DRIVER_GPIO = "gpio"
CONF_DRIVER_PCA9685 = "pca9685"
CONF_DRIVER_TYPES = [CONF_DRIVER_GPIO, CONF_DRIVER_PCA9685]
