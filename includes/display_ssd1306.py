#!/usr/bin/env python3

import board
import busio
import adafruit_ssd1306
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from time import sleep

import threading


# Code for the OLED Display
#   SSD 1306


class OLED_Device:
    
    def __init__(self, param_scl_pin = False, param_sda_pin = False):
        # use the pin numbers
        #   of the default pins for I2C
        if False == param_scl_pin:
            scl_pin   = board.SCL
        else:
            scl_pin   = param_scl_pin
        if False == param_sda_pin:
            sda_pin   = board.SDA
        else:
            sda_pin   = param_sda_pin
        reset_pin = None
    
        i2c_con = busio.I2C(scl_pin, sda_pin)
    
        i2c_addr    = 0x3c
        self.width  = 128
        self.height = 64
        
        self.display =  adafruit_ssd1306.SSD1306_I2C(
                width  = self.width,
                height = self.height, 
                i2c    = i2c_con,
                addr   = i2c_addr,
                reset  = reset_pin)
    def blank(self):
        # Clear display.
        self.display.fill(0)
        self.display.show()


class OLED_Image:
    def __init__(self, oled):
        self.width  = oled.width
        self.height = oled.height
        self.oled   = oled

        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        self.image  = Image.new("1", (self.width, self.height))
    
        # Get drawing object to draw on image.
        self.draw = ImageDraw.Draw(self.image)

    def draw_background(self, monochrome_color):

        if monochrome_color == 0 or monochrome_color is None:
            monochrome_color = 0
        else:
            monochrome_color = 255
        # Draw a white background
        self.draw.rectangle((0, 0, self.width, self.height),
           outline=monochrome_color, fill=monochrome_color)

    def apply(self):
        # Display image
        self.oled.display.image(self.image)
        self.oled.display.show()

    def write_text(self, text, font_size = 12, pos_horizontal = "center", pos_vertical = "middle"):
        # Load default font.
        #font = ImageFont.load_default()
        font = ImageFont.truetype(
                font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                size = font_size,
                index = 0,
                encoding = 'unic'
               )
        
        # Draw Some Text
        (font_width, font_height) = font.getsize(text)
        x = 0
        y = 0
        if "left" == pos_horizontal:
            x = 0
        elif "center" == pos_horizontal:
            x = self.width // 2
            x -= font_width // 2
        elif "right" == pos_horizontal:
            x = self.width - font_width
        else:
            x = int(pos_horizontal)
        if "top" == pos_vertical:
            y = 0
        elif "middle" == pos_vertical:
            y = self.height // 2
            y -= font_height // 2 
        elif "bottom" == pos_vertical:
            y = self.height - font_height
        else:
            y = int(pos_vertical)


        self.draw.text(
            (x, y), 
            text,
            font=font,
            fill=255
        )
        # return the bounding box
        return (x, y, font_width, font_height)
        

def get_hh_mm_ss():
    dt = datetime.now()
    return "{:02d}:{:02d}:{:02d}".format(dt.hour, dt.minute, dt.second)

def get_cpu_temp():
    temp_raw = None
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as fd:
        temp_raw = fd.read()
    return float(temp_raw)/1000

def get_timestamp():
    return datetime.now().timestamp()


class OLED_Printing(threading.Thread):
    def __init__(self, i2c_scl_pin, i2c_sda_pin):
        super(OLED_Printing, self).__init__()
        
        self.oled = OLED_Device(i2c_scl_pin, i2c_sda_pin)
        self.last_update_time = get_timestamp()
        self.display_text = ""
        self.keep_running = False

    def initialize(self):
        pass

    def run(self):
        self.keep_running = True
        try:
            interval_time = 1
            painting_time = 0
        
            while self.keep_running:
                painting_time = get_timestamp()
        
                curImage = OLED_Image(self.oled)
                curImage.draw_background(0x00)
                nowString = get_hh_mm_ss()
                curImage.write_text(nowString, 28, "center", "top")
                if 0 == len(self.display_text):
                    cpuTempString = "CPU: {:.1f} C".format(get_cpu_temp())
                    curImage.write_text(cpuTempString, 16, "left", "bottom")
                else:
                    i = 0
                    for curline in self.display_text.split("\n"):
                        curImage.write_text(curline, 16, "left", 30 + (i * 18))
                        i = i + 1
                #print("Trying to paint to OLED...")
                curImage.apply()
                right_now = get_timestamp()
                self.last_update_time = right_now
        
                painting_time = right_now - painting_time
                #print("Painting Time {:1.3f}".format(painting_time))
                until_next_full_second = float(1_000_000 - datetime.now().microsecond) / 1_000_000
        
                if 0.0 < until_next_full_second:
                    sleep(until_next_full_second)
                else:
                    pass
        except KeyboardInterrupt:
            print("User interrupt.")
        
        except Exception as excObj:
            print("Some error occured")
            print(excObj)
        self.finalize() 

    def store_reading(self, text):
        self.display_text = text

    def finalize(self):
        self.keep_running = False
        print("Clearing OLED display")
        self.oled.blank()
