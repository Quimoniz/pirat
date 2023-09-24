


i2c_dependencies:
	bash -c "if lsmod | grep -qi i2c; then \
		echo 'You need to enable I2C in the' \
		echo 'Raspberry Pi config...' \
		echo '  [press enter for launching that]' \
		read; \
		sudo raspi-config \
		fi"

python_dependencies:
	sudo apt-get install -y python3-pil
	sudo apt-get install -y i2c-tools
	pip3 install --user adafruit-circuitpython-ssd1306
	pip3 install --user sdnotify

dependencies: i2c_dependencies python_dependencies


UID := $(shell id -u)
install: 
	sudo systemctl stop motion-detect.service || true
	sudo systemctl disable motion-detect.service || true
	sed "s:/home/pi/git-pirat:${CURDIR}:; s/1000/${UID}/;" motion-detect.service
	sudo systemctl enable ${CURDIR}/motion-detect.service
	sudo systemctl start motion-detect.service
