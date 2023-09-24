#!/usr/bin/env python3

import RPi.GPIO as GPIO
import board
import time
import os
import datetime
import sys
import subprocess

import threading
from collections import deque
# library for notifying systemd about proper startup
import board
#   pip3 install --user sdnotify
import sdnotify

from lib.display_ssd1306 import OLED_Printing

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



# Nice tutorial on Threading in Python
#   https://superfastpython.com/threading-in-python/
class ContinuousUSObservation(threading.Thread):
    def __init__(self, trigger_pin, echo_pin):
        super(ContinuousUSObservation, self).__init__()

        self.keep_running = True
        self.iteration_counter = 1
        self.COLUMN_MAX = 60
        self.clear_this_many_chars = -1
        #self.last_alert_timestamp = 0
        #self.approachment_small_distance = 100

        #self.min_time_between_activations = 180 #180
        #self.unactivate_timeout = 300
        #self.activate_state = 0

        self.pause_between_uniform = 1.0

        self.ultra_trigger_pin = trigger_pin
        self.ultra_echo_pin    = echo_pin
        self.setup_state    = 0
        self.distance_deque = deque(maxlen = 20)
        self.consecutive_measurement_fails = 0
        self.activity_callbacks = []

    def initialize(self):
        if 0 == self.setup_state:
            # setup the ultra sonic sensor:
            try:
                GPIO.setup (self.ultra_trigger_pin, GPIO.OUT)
                GPIO.setup (   self.ultra_echo_pin, GPIO.IN )
                GPIO.output(self.ultra_trigger_pin, False)
                self.setup_state = 1
            except RuntimeWarning:
                print("Can not initialize Ultra Sonic Sensor, the GPIO pins ({}, {}) seem to be locked.".format(self.ultra_trigger_pin, self.ultra_echo_pin))
                print("You might want to manually free them using")
                print("the command 'GPIO.cleanup([{}, {}]'".format(self.ultra_trigger_pin, self.ultra_echo_pin))
        else:
            print("Bad setup state {}, can't initialize in a different state than zero.".format(self.setup_state))

    # Overrides the Thread classes' run() method
    def run(self):
        self.initialize()
        while self.keep_running:
            self.single_observation()
            # TODO(some day...): put the activation logic into a separate thread
            #       the activation step could be locking a mutex
            #       so reactivations while already being activated
            #       would be avoided, as the mutex would already be locked
            #self.check_for_activate_reason()
            #self.check_for_unactive_reason()
        
            try:
                time.sleep(self.pause_between_uniform)
            except KeyboardInterrupt:
                self.keep_running = False
        self.finalize()
#    def proximity_noticed(self):
#        if self.distance_deque[-1] \
#          and self.distance_deque[-1] < self.approachment_small_distance \
#          and self.distance_deque[-2] \
#          and self.distance_deque[-2] < self.approachment_small_distance:
#            return True
#        else:
#            return False
#
#    def check_for_activate_reason(self):
#        if 0 == self.activate_state:
#            if self.proximity_noticed():
#                stamp = datetime.datetime.now().timestamp()
#                if (self.last_alert_timestamp + self.min_time_between_activations) < stamp:
#                    self.last_alert_timestamp = stamp
#                    self.activate_state = 1
#                    do_activation()
#
#    # TODO (some day...): have the stop of the activation phase in
#    #     a separate thread, such that we don't have to check each iteration
#    #     for whether our time already elapsed, but instead have the thread
#    #     sleep for the duration of activation phase, whereupon of course the
#    #     activation phase is being ended 
#    # DONE: before ending the activation phase, we might seriously
#    #     want to check whether an immediate reactivation is probably coming.
#    #     (i.e. it's ugly if we go into deactivated state, yet are being woken up
#    #     just the next second, because activation reason is being found
#    def check_for_unactive_reason(self):
#        if 1 == self.activate_state:
#            stamp = datetime.datetime.now().timestamp()
#            if stamp > (self.last_alert_timestamp + self.unactivate_timeout):
#                if self.proximity_noticed():
#                    self.last_alert_timestamp = stamp
#                else:
#                    self.activate_state = 0
#                    do_unactivation()


    def single_observation(self):
        if 1 == self.setup_state:
            current_distance = self.measure_distance()
            self.distance_deque.append(current_distance)
            if False != current_distance:
                for cur_callback in self.activity_callbacks:
                    call_obj, call_func, callCondition = cur_callback
                    if current_distance < callCondition:
                        call_func("us", current_distance)
   
# TODO (some day...): maybe we want to log the distance values, e.g. to a grafana database?
#                print("{} cm".format(round(current_distance * 10) / 10))

        else:
            print("Bad setup state {}, can't observe sensor in a different state than one.".format(self.setup_state))
            print("Ending myself")
            self.keep_running = False
        self.iteration_counter += 1

    def measure_distance(self):
    
        measurement_successfull = True
    
        # initiate a distance measurement
        # by sending a 10 microsecond long trigger signal
        GPIO.output(self.ultra_trigger_pin, True)
        time.sleep(0.000_01)
        GPIO.output(self.ultra_trigger_pin, False)
    
        start_time         = 0
        end_time           = 0
        delta_time         = 0
        min_sleep_duration = 0.000_002
        # the sleep multiplied by the number below
        #   should be above 0.017492 seconds
        #   which is 300 centimeters (the maximum measuring distance)
        #   In this case ten thousand iterations
        #   multiplied by 2 microseconds is equal to 0.02 seconds
        max_while          = 10_000
        sensor_replies_in_time = True
    
        try:
            while_counter = 0
            start_time = time.time()
            while GPIO.input(self.ultra_echo_pin) == 0:
                start_time = time.time()
                time.sleep(min_sleep_duration)
                while_counter = while_counter + 1
                if while_counter > max_while or not self.keep_running:
                    sensor_replies_in_time = False
                    break
    
            if sensor_replies_in_time and self.keep_running:
                while_counter = 0
                end_time = start_time
                while GPIO.input(self.ultra_echo_pin) == 1:
                    end_time = time.time()
                    time.sleep(min_sleep_duration)
                    while_counter = while_counter + 1
                    if while_counter > max_while or not self.keep_running:
                        sensor_replies_in_time = False
                        break
    
        except KeyboardInterrupt:
            self.keep_running = False
            measurement_successfull = False
    
        
        if sensor_replies_in_time:
            delta_time = end_time - start_time
        
            # calculate distance based on speed of sound
            distance = float((delta_time * 34300) / 2)
        
            if distance < 2 and distance >= 300:
               measurement_successfull = False

            if 0 < self.consecutive_measurement_fails:
                print("Ultra Sonic sensor recovered, measuring {:.1f} cm.".format(distance))
                print(" - we had {} failed measurements in the last {:.1f} seconds before that".format(
                    self.consecutive_measurement_fails,
                    self.consecutive_measurement_fails * self.pause_between_uniform)
                    )
                self.consecutive_measurement_fails = 0
        else:
            if 0 == self.consecutive_measurement_fails:
                print("Ultra Sonic Sensor does not reply in time,")
                print("  i.e. end_time - start_time = {:.2f}".format(end_time - start_time))
            elif 1 == self.consecutive_measurement_fails:
                print("Ultra Sonic Sensor does not reply in time again,")
                print("  i.e. end_time - start_time = {:.2f}".format(end_time - start_time))
                print("  ceasing to report on each measurement, reporting again,")
                print("  once a measurement we do, does return successfully.")
            elif 600 == self.consecutive_measurement_fails:
                print("Ultra Sonic Sensor did not get any sensible reading again, the latest was:")
                print("  i.e. end_time - start_time = {:.2f}".format(end_time - start_time))
                print("  and this is going on for the last 600 measurements ({:.1f} seconds)".format(
                    600.00 * self.pause_between_uniform)
                    )
            elif 0 == (self.consecutive_measurement_fails % 7200):
                print("Ultra Sonic Sensor does not reply in time again,")
                print("  there was not a single successfull measurement in the last")
                print("  {:.1f} seconds, minimal reporting, for the time being now.".format(
                    self.consecutive_measurement_fails * self.pause_between_uniform))
                print("  For reference the last failed measurement")
                print("  was end_time - start_time = {:.2f}".format(end_time - start_time))
            self.consecutive_measurement_fails += 1
            measurement_successfull = False
    
    
        if measurement_successfull:
            if False:
                if 0 < self.clear_this_many_chars:
                    print("\x1b[2K\x1b[{}D".format(self.clear_this_many_chars), end='')
                number_to_print = "{:>1F}".format(distance)
                self.clear_this_many_chars = len(number_to_print)
                print(number_to_print, end = '')
                sys.stdout.flush()
            return distance
        else:
            return False
    
    def finalize(self):
        if 1 == self.setup_state:
            self.keep_running = False
            GPIO.cleanup([self.ultra_trigger_pin, self.ultra_echo_pin])
            self.setup_state = 2
        else:
            print("Can't un-setup myself, when setup state does not indicate that setup was run.")
    def subscribe_to_activity(self, foreignObject, foreignCallback, relevantMinDistance):
        self.activity_callbacks.append((foreignObject, foreignCallback, relevantMinDistance))

    def get_reading(self):
        text = "Usonic: "
        if self.distance_deque[-1]:
             text = "{}{:.1f} cm".format(text, self.distance_deque[-1])
        else:
             text = text + "---"
        return text



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
        nice_pir_state = "False 🕶️"
        if self.pir_state:
            nice_pir_state = "True 👀"
        return "PIR: {}".format(nice_pir_state)




class StandbyController:
    def __init__(self, observers):
        self.sensor_observers = observers

        self.last_alert_timestamp            = 0
        self.last_activity_noticed_timestamp = 0
        self.last_activity_noticed_source    = 0
        self.min_time_between_activations    = 10 #180
        self.unactivate_timeout              = 300
        self.activate_state                  = 0
        self.action_thread                   = None

        for cur_sensor_observer in self.sensor_observers:
            if isinstance(cur_sensor_observer, ContinuousUSObservation):
                cur_sensor_observer.subscribe_to_activity(self, self.activity_noticed, 100)
            else:
                cur_sensor_observer.subscribe_to_activity(self, self.activity_noticed)
            cur_sensor_observer.start()
    def get_reading(self):
        multiline_text = ""
        for cur_sensor_observer in self.sensor_observers:
           multiline_text = multiline_text + cur_sensor_observer.get_reading() + "\n"
        return multiline_text

    def activity_noticed(self, sensor_type_string, sensor_data=None):
        self.record_activity((sensor_type_string, sensor_data))
        if 0 == self.activate_state:
            stamp = self.__mk_timestamp()
            if (self.last_alert_timestamp + self.min_time_between_activations) < stamp:
                self.last_alert_timestamp = stamp
                self.compile_wakeup_message()
                self.defer_activation()

    def __mk_timestamp(self):
        return datetime.datetime.now().timestamp()

    def record_activity(self, activity_source):
        self.last_activity_noticed_timestamp = self.__mk_timestamp()
        self.last_activity_noticed_source    = activity_source
        # DEBUG:
        # print("Record activity: {}".format(repr(activity_source)))

    def check_standby_elligibility(self):
        stamp = self.__mk_timestamp()
        if (self.last_activity_noticed_timestamp + self.unactivate_timeout) < stamp:
            if 1 == self.activate_state:
                self.defer_deactivation()

    def compile_wakeup_message(self):
        reason_str = ""
        additional_reason = "something "
        if isinstance(self.last_activity_noticed_source, tuple):
            reason_str = str(self.last_activity_noticed_source[0])
            if 2 <= len(self.last_activity_noticed_source) \
            and self.last_activity_noticed_source[1] is not None:
                if "us" in reason_str:
                    additional_reason = "({:<3f} cm) ".format(self.last_activity_noticed_source[1])
                else:
                    additional_reason = "(" + str(self.last_activity_noticed_source[1]) + ") "

        else:
            reason_str = repr(self.last_activity_noticed_source)

        time_str = str(datetime.datetime.now())

        print("Waking up: Sensor \"{sens_type:^4s}\" noticed {additional:^10s}at {timestring}".format(sens_type=reason_str, additional=additional_reason, timestring=time_str))
        sys.stdout.flush()
        
    def defer_activation(self):
        self.activate_state = 1

        if self.action_thread is None:
            self.action_thread = ActionThread("activation",   self.action_finished_callback)
            self.action_thread.start()

    def defer_deactivation(self):
        self.activate_state = 0
        if self.action_thread is None:
            self.action_thread = ActionThread("deactivation", self.action_finished_callback)
            self.action_thread.start()

    def action_finished_callback(self):
        self.action_thread = None


    def finalize(self):
        for cur_sensor_observer in self.sensor_observers:
            cur_sensor_observer.keep_running = False

        for cur_sensor_observer in self.sensor_observers:
            cur_sensor_observer.join()

    def join(self):
        for cur_sensor_observer in self.sensor_observers:
            cur_sensor_observer.join()


class ActionThread (threading.Thread):
    def __init__(self, action_to_perform, report_finished_func_callback):
        super(ActionThread, self).__init__()
        self.keep_running         = True
        self.action_name          = action_to_perform
        self.report_finished_func = report_finished_func_callback
    def initialize(self):
        pass
    def run(self):
        self.initialize()
        self.do_printout("Action started: {}".format(self.action_name))
        try:
            if "activation" == self.action_name:
                self.do_activation()
            elif "deactivation" == self.action_name:
                self.do_deactivation()
        except:
            print("Some issue occured, while executing some external component.")
        self.do_printout("Action ended: {}".format(self.action_name))
        
        self.finalize()

    def finalize(self):
        self.report_finished_func()

    def do_deactivation(self):
        self.do_printout("Going back to standby at  {}".format(str(datetime.datetime.now())))
        self._run_cmd("xset", 
           {'DISPLAY': ':0'},
           'xset s activate')
    def do_activation(self):
#        self._run_cmd("printenv",
#           {'XDG_RUNTIME_DIR': '/run/user/{}'.format(os.getuid()),
#            'PULSE_RUNTIME_PATH': '/run/user/{}/pulse/'.format(os.getuid()),
#           'DISPLAY': ':0'},
#           'printenv')
        self._run_cmd("xset",
           {'DISPLAY': ':0'},
           'xset s reset')
        time.sleep(0.5)
        self._run_cmd("xset",
           {'DISPLAY': ':0'},
           'xset s default')
        time.sleep(1)
        #  bash -c "XDG_RUNTIME_DIR=/run/user/1000 paplay win95_startup.wav"
        # Note: Pulseaudio has 100 % volume being 65568
        self._run_cmd("paplay",
           {'XDG_RUNTIME_DIR': '/run/user/{}'.format(os.getuid()),
            'PULSE_RUNTIME_PATH': '/run/user/{}/pulse/'.format(os.getuid()),
            'LC_ALL': 'C'},
            'paplay --volume=20000 win95_startup.wav',
            timeout = 10)
            #'cvlc win95_startup.wav')
    def _run_cmd(self, shortname, environment, cmdline, timeout = 4):
        #print('cmdline: {}'.format(cmdline))
        env_string = ""
        for cur_key in environment.keys():
            env_string = '{} {}="{}" '.format(env_string, cur_key, environment[cur_key])

        sub_process = None
        sub_output  = ""
        sub_error   = ""
        try:
            sub_process = subprocess.Popen(cmdline,
                  shell=True,
                  env=environment,
                  stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE,
                  encoding='utf-8')
            sub_output, sub_error = sub_process.communicate(timeout = timeout)
        except subprocess.TimeoutExpired:
            self.do_printout("Process ran into timeout, killing it. We invoked {}".format(cmdline))
            with sub_process.stdout as fd:
               sub_output = fd.read()
            with sub_process.stderr as fd:
               sub_error = fd.read()
            sub_process.kill()
        except:
           self.do_printout("Some issue occured when trying to invoke {}".format(cmdline))

        if 0 < len(sub_output):
            self.do_printout("Running {} caused this output:\n{}".format(shortname, sub_output))
        if 0 < len(sub_error):
            self.do_printout("Running {} caused this error:\n{}".format (shortname, sub_error))
         
    def do_printout(self, msg):
        print(msg)
        sys.stdout.flush()

            

        
# TODO: unify the PIR observation and the Ultrasonic Observation
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
while global_keep_running:
    try:
        systemd_notify.notify("STATUS=ping...")
        controller.check_standby_elligibility()
        display.store_reading(controller.get_reading())
#        print(".", end="")
#        sys.stdout.flush()
        time.sleep(1)
    except KeyboardInterrupt:
        global_keep_running = False
        #TODO:
        #observer.keep_running = False
        print("\nCaught KeyboardInterrupt, unlocking the GPIO pins...")

controller.finalize()       
display.finalize()

# Waiting for potential outstanding measurements to finish
#   also gives it time to finalize itself, which frees
#   the lock on the GPIO pins (which is necessary to be
#     able to use them again, without having to reboot)
controller.join()
display.join()





