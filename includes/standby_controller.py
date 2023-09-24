import datetime
import sys
from .ultrasonic_sensor import ContinuousUSObservation
from .action_thread import ActionThread


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

