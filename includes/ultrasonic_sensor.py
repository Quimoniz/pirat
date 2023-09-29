import RPi.GPIO as GPIO
import time
import sys
import subprocess
import threading
from collections import deque


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
            # TODO(some day...): put the activation logic into a separate thread (that is done)
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
#    # Idea: have the stop of the activation phase in
#    #     a separate thread, such that we don't have to check each iteration
#    #     for whether our time already elapsed, but instead have the thread
#    #     sleep for the duration of activation phase, whereupon of course the
#    #     activation phase is being ended
#    #   We still check the standby controller's 'check_standby_elligibility()' on each iteration of our main loop
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
             text = "{}{:3.1f} cm".format(text, self.distance_deque[-1])
        else:
             text = text + "---"
        return text
