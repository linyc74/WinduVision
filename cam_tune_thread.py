import numpy as np
import cv2, time, sys, math, json
from abstract_thread import *



class CamTuneThread(AbstractThread):

    def __init__(self, cap_thread, mediator):

        super(CamTuneThread, self).__init__()

        self.cap_thread = cap_thread
        self.mediator = mediator

        self.connect_signals(mediator = mediator,
                             signal_names = ['auto_cam_resumed',
                                             'auto_cam_paused' ,
                                             'set_info_text'   ,
                                             'update_cam_parm' ])

        self.__init__parameters()

    def __init__parameters(self):

        with open('parameters/auto_cam.json', 'r') as fh:
            parms = json.loads(fh.read())

        L = ['goal',
             'tolerance', # i.e. goal +/- tolerance
             'learn_rate', # learning rate for adjusting gain
             'gain_max',
             'gain_min',
             'exposure_max',
             'exposure_min']

        for name in L:
            setattr(self, name, parms[name])

    def main(self):

        self.check_gain()
        self.check_exposure()

        gain = self.cap_thread.get_one_cam_parm('gain')
        exposure = self.cap_thread.get_one_cam_parm('exposure')
        img = self.get_roi(self.cap_thread.get_image())
        mean = np.average(img)

        self.emit_info(mean)

        diff = self.goal - mean

        # Control the frequency of the main loop according to the difference.
        if abs(diff) > self.tolerance:
            time.sleep(0.1)
        else:
            time.sleep(1)

        # Dynamically adjust gain according to the difference
        if diff > self.tolerance:
            gain += (int(diff * self.learn_rate) + 1)

        elif diff < (-1 * self.tolerance):
            gain += (int(diff * self.learn_rate) - 1)

        else:
            return # Do nothing if it's within tolerated range

        # If gain out of range, adjust exposure without adjusting gain
        if gain > self.gain_max:
            exposure = exposure - 1 # exposure brighter
            if exposure >= self.exposure_min:
                self.set_cam(name='exposure', value=exposure)
                self.set_cam(name='gain', value=self.gain_min)
                time.sleep(0.1) # Takes a while before the exposure change takes effect
            return

        elif gain < self.gain_min:
            exposure = exposure + 1 # exposure darker
            if exposure <= self.exposure_max:
                self.set_cam(name='exposure', value=exposure)
                self.set_cam(name='gain', value=self.gain_max)
                time.sleep(0.1)
            return

        else:
            self.set_cam(name='gain', value=gain)

    def check_gain(self):

        gain = self.cap_thread.get_one_cam_parm('gain')

        if gain < self.gain_min:
            self.set_cam(name='gain', value=self.gain_min)
        elif gain > self.gain_max:
            self.set_cam(name='gain', value=self.gain_max)

    def check_exposure(self):

        exposure = self.cap_thread.get_one_cam_parm('exposure')

        if exposure < self.exposure_min:
            self.set_cam(name='exposure', value=self.exposure_min)
        elif exposure > self.exposure_max:
            self.set_cam(name='exposure', value=self.exposure_max)

    def emit_info(self, mean):

        text = 'Tuning camR image mean: {}'.format(mean)

        data = {'line': 4,
                'text': text}

        self.mediator.emit_signal( signal_name = 'set_info_text',
                                   arg = data )

    def set_cam(self, name, value):
        ret = self.cap_thread.set_one_cam_parm(name, value)
        if ret:
            self.update_gui(name)

    def update_gui(self, name):
        which_cam = self.cap_thread.get_which_cam()

        data = {'which_cam': which_cam,
                'name': name}

        self.mediator.emit_signal('update_cam_parm', data)

    def before_resuming(self):
        self.mediator.emit_signal(signal_name = 'auto_cam_resumed')
        return True

    def after_paused(self):
        self.mediator.emit_signal(signal_name = 'auto_cam_paused')
        return True

    def get_roi(self, img):

        rows, cols, channels = img.shape

        A = rows * 1 / 4
        B = rows * 3 / 4
        C = cols * 1 / 4
        D = cols * 3 / 4

        return img[A:B, C:D, :]

    def set_cap_thread(self, thread):
        self.cap_thread = thread


