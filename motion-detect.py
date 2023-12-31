#!/usr/bin/env python3

import RPi.GPIO as GPIO
import board
import time
import os
import signal
#import sys
#import subprocess

# library for notifying systemd about proper startup
import board
#   pip3 install --user sdnotify
import sdnotify

from includes.display_ssd1306 import OLED_Printing
from includes.action_thread import ActionThread
from includes.pir_sensor import ContinuousPIRObservation
from includes.ultrasonic_sensor import ContinuousUSObservation
from includes.standby_controller import StandbyController

#import datetime

global_got_sig_usr1 = False
global_got_sig_usr2 = False

def handle_sig_usr1(signum, frame):
    global_got_sig_usr1 = True

def handle_sig_usr2(signum, frame):
    global_got_sig_usr2 = True



signal.signal(signal.SIGUSR1, handle_sig_usr1)
signal.signal(signal.SIGUSR2, handle_sig_usr2)


def main():
    GPIO.setmode(GPIO.BCM)
    #pir_pin = 4
    
    #https://www.instructables.com/GPIOs-More-Python/
    #https://pypi.org/project/RPi.GPIO/
    #https://sourceforge.net/p/raspberry-gpio-python/wiki/Inputs/
    #GPIO.setup(pir_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    #input_signal = GPIO.input(pir_pin)
    #if input_signal:
    #    print("PIR Signal is HIGH")
    #else:
    #    print("PIR Signal is HIGH")
    #print("input_signal:{}".format(input_signal))
    
    
    systemd_notify = sdnotify.SystemdNotifier()
    # DONE: unified the PIR observation and the Ultrasonic Observation
    #       consider using the Observer Pattern: https://en.wikipedia.org/wiki/Observer_pattern
    #ContinuousPIRObservation(pir_pin = 23)
    
    #observer = ContinuousUSObservation(17, 27)
    #observer.start()
    
    #controller = StandbyController([ContinuousUSObservation(trigger_pin = 17, echo_pin = 27), ContinuousPIRObservation(pir_pin = 23)])
    controller = StandbyController([ContinuousUSObservation(trigger_pin = 18, echo_pin = 23), ContinuousPIRObservation(pir_pin = 15)])
    display    = OLED_Printing(board.SCL, board.SDA)
    
    global_keep_running = True
    systemd_notify.notify("MAINPID={}".format(os.getpid()))
    systemd_notify.notify("READY=1")
    
    display.start()
    counter = 1
    while global_keep_running:
        try:
            #print("MAIN: A")
            systemd_notify.notify("STATUS=ping...")
            if global_got_sig_usr1:
                print("Doing manual activation")
                controller.defer_activation()
                global_got_sig_usr1 = False
            if global_got_sig_usr2:
                print("Doing manual deactivation")
                controller.defer_deactivation()
                global_got_sig_usr2 = False
            #print("MAIN: B {}".format(datetime.datetime.now()))
            controller.check_standby_elligibility()
            #print("MAIN: C {}".format(datetime.datetime.now()))
            display.store_reading(controller.get_reading())
            #print("MAIN: D {}".format(datetime.datetime.now()))
    #        print(".", end="")
    #        sys.stdout.flush()
#            if 0 == (counter % 30):
#                print("Just checked standby elligibility")
            time.sleep(1)
        except KeyboardInterrupt:
            global_keep_running = False
            #TODO:
            #observer.keep_running = False
            print("\nCaught KeyboardInterrupt, unlocking the GPIO pins...")
        counter += 1
    controller.finalize()       
    display.finalize()
    
    # Waiting for potential outstanding measurements to finish
    #   also gives it time to finalize itself, which frees
    #   the lock on the GPIO pins (which is necessary to be
    #     able to use them again, without having to reboot)
    controller.join()
    display.join()


if "__main__" == __name__:
    main()


