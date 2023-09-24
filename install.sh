sudo apt-get install python3-pil
sudo apt-get install i2c-tools
echo "You need to enable I2C in the"
echo "Raspberry Pi config..."
echo "  [press enter for launching that]"
read;
sudo raspi-config
pip3 install --user adafruit-circuitpython-ssd1306
pip3 install --user sdnotify
