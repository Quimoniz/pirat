import time
import datetime
import sys
import os
import threading
import subprocess
import traceback


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
        except Exception as exc:
            print("Some issue occured, while executing some external component.")
            traceback.print_exc()
        self.do_printout("Action   ended: {}".format(self.action_name))
        
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

