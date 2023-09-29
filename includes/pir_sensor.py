import RPi.GPIO as GPIO
import board
import time
import sys
import subprocess
import threading


class ContinuousPIRObservation(threading.Thread):
    def __init__(self, pir_pin):
        super(ContinuousPIRObservation, self).__init__()

        self.pir_pin = pir_pin
        self.keep_running = True
        self.setup_state    = 0
        self.iteration_counter = 1
        self.COLUMN_MAX = 60
        self.activity_callbacks = []
        self.pir_state = False

    def initialize(self):
        if 0 == self.setup_state:
            #https://www.instructables.com/GPIOs-More-Python/
            #https://pypi.org/project/RPi.GPIO/
            #https://sourceforge.net/p/raspberry-gpio-python/wiki/Inputs/
            GPIO.setup(self.pir_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            self.setup_state = 1
        else:
            print("Bad setup state {}, can't initialize in a different state than zero.".format(self.setup_state))
    def finalize(self):
        if 1 == self.setup_state:
            GPIO.cleanup(self.pir_pin)
            self.setup_state = 2
        else:
            print("Can't un-setup myself, when setup state does not indicate that setup was run.")
            
    def run(self):
        self.initialize()
        while self.keep_running:
            self.pir_state = GPIO.input(self.pir_pin)
            if self.pir_state:
                print("PIR")
                for cur_entry in self.activity_callbacks:
                    call_obj, call_func = cur_entry
                    call_func("pir")

            if False:
                if self.pir_state:
                    print("[41m,[40m", end = '')
                else:
                    print(".", end = '')
            
                if (self.iteration_counter % self.COLUMN_MAX) == 0:
                    print()
            
                sys.stdout.flush()
            try:
                time.sleep(0.2)
            except KeyboardInterrupt:
                keep_running = False
            self.iteration_counter += 1
        self.finalize()

    def subscribe_to_activity(self, foreignObject, foreignCallback):
        self.activity_callbacks.append((foreignObject, foreignCallback))
    def get_reading(self):
        # "False 🕶️"
        nice_pir_state = "nope"
        if self.pir_state:
            # "True 👀"
            nice_pir_state = " yup"
        return "PIR: {}".format(nice_pir_state)
