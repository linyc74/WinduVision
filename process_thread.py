import numpy as np
import cv2, time, sys, threading, json
from constants import *



class ProcessThread(threading.Thread):

    def __init__(self, capture_thread_R, capture_thread_L, mediator):
        super(ProcessThread, self).__init__()

        # Mediator emits signal to the gui object
        self.mediator = mediator

        self.capture_thread_R = capture_thread_R
        self.capture_thread_L = capture_thread_L

        self.__init__signals(connect=True)
        self.__init__parms()

    def __init__signals(self, connect=True):
        '''
        Call the mediator to connect signals to the gui.
        These are the signals to be emitted dynamically during runtime.

        Each signal is defined by a unique str signal name.

        The parameter 'connect' specifies whether connect or disconnect signals.
        '''
        signal_names = ['display_image', 'recording_starts', 'recording_ends', 'set_info_text']

        if connect:
            self.mediator.connect_signals(signal_names)
        else:
            self.mediator.disconnect_signals(signal_names)

    def __init__parms(self):
        # Parameters for image processing
        self.offset_x, self.offset_y = 0, 0

        self.zoom = 1.0

        with open('parameters/gui.json', 'r') as fh:
            gui_parms = json.loads(fh.read())
        self.display_width = gui_parms['default_width']
        self.display_height = gui_parms['default_height']

        self.set_resize_matrix()



        # Parameters for stereo depth map
        self.ndisparities = 32 # Must be divisible by 16
        self.SADWindowSize = 31 # Must be odd, be within 5..255 and be not larger than image width or height



        # Parameters for looping, control and timing
        self.recording = False
        self.stopping = False
        self.pausing = False
        self.isPaused = False
        self.computingDepth = False
        self.t_series = [time.time() for i in range(30)]
        self.fps = 30.0

    def set_resize_matrix(self):
        '''
        Define the transformation matrix for the image processing pipeline.
        Also define the dimension of self.imgDisplay, which is the terminal image to be displayed in the GUI.
        '''

        img = self.capture_thread_R.get_image()
        img_height, img_width, _ = img.shape

        display_height, display_width = self.display_height, self.display_width

        # The height-to-width ratio
        h_w_ratio_img = float(img_height) / img_width
        h_w_ratio_display = float(display_height) / (display_width / 2)

        # The base scale factor is the ratio of display size / image size,
        #     which scales the image to the size of the display.

        if h_w_ratio_img > h_w_ratio_display:
            base_scale = float(display_height) / img_height
        else:
            base_scale = float(display_width/2) / img_width



        # The actual scale factor is the product of the base scale factor and the zoom factor.
        scale_x = base_scale * self.zoom
        scale_y = base_scale * self.zoom



        # The translation distance for centering
        #     = half of the difference between
        #         the screen size and the zoomed image size
        #    ( (     display size     ) - (     zoomed image size   ) ) / 2
        tx = ( (display_width / 2) - (img_width  * scale_x) ) / 2
        ty = ( (display_height   ) - (img_height * scale_y) ) / 2



        # Putting everything together into a matrix
        Sx = scale_x
        Sy = scale_y

        Off_x = self.offset_x
        Off_y = self.offset_y

        # For the right image, it's only scaling and centering
        self.resize_matrix_R = np.float32([ [Sx, 0 , tx] ,
                                            [0 , Sy, ty] ])

        # For the left image, in addition to scaling and centering, the offset is also applied.
        self.resize_matrix_L = np.float32([ [Sx, 0 , Sx*Off_x + tx] ,
                                            [0 , Sy, Sy*Off_y + ty] ])



        # Define the dimensions of:
        #     self.imgR_proc  --- processed R image to be accessed externally
        #     self.imgL_proc  ---           L image
        #     self.imgDisplay --- display image to be emitted to the GUI object
        rows, cols = self.display_height, self.display_width
        self.imgR_proc  = np.zeros((rows, cols/2, 3), np.uint8)
        self.imgL_proc  = np.zeros((rows, cols/2, 3), np.uint8)
        self.imgDisplay = np.zeros((rows, cols  , 3), np.uint8)

    def run(self):
        '''
        There are three major steps for the image processing pipeline,
        with some additional steps in between.

        ( ) Check image dimensions.
        (1) Eliminate offset of the left image.
        (2) Resize and translate to place each image at the center of both sides of the view.
        ( ) Compute depth map (optional).
        (3) Combine images.
        '''

        t0 = time.clock()

        while not self.stopping:

            # Pausing the loop (or not)
            if self.pausing:
                self.isPaused = True
                time.sleep(0.1)
                continue
            else:
                self.isPaused = False



            # Get the images from self.capture_thread
            self.imgR_0 = self.capture_thread_R.get_image() # The suffix '_0' means raw input image
            self.imgL_0 = self.capture_thread_L.get_image()

            # Quick check on the image dimensions
            # If not matching, skip and continue
            if not self.imgR_0.shape == self.imgL_0.shape:
                self.mediator.emit_signal( signal_name = 'set_info_text',
                                           arg = 'Image dimensions not identical.' )
                time.sleep(0.1)
                continue



            # (1) Eliminate offset of the left image.
            # (2) Resize and translate to place each image at the center of both sides of the view.
            rows, cols = self.display_height, self.display_width / 2 # Output image dimension

            self.imgR_1 = cv2.warpAffine(self.imgR_0, self.resize_matrix_R, (cols, rows))
            self.imgL_1 = cv2.warpAffine(self.imgL_0, self.resize_matrix_L, (cols, rows))

            # Update processed images for external access
            self.imgR_proc[:,:,:] = self.imgR_1[:,:,:]
            self.imgL_proc[:,:,:] = self.imgL_1[:,:,:]



            # Compute stereo depth map (optional)
            if self.computingDepth:
                self.imgL_1 = self.compute_depth(self.imgR_1, self.imgL_1)



            # (3) Combine images.
            h, w = self.display_height, self.display_width
            self.imgDisplay[:, 0:(w/2), :] = self.imgL_1
            self.imgDisplay[:, (w/2):w, :] = self.imgR_1

            self.mediator.emit_signal( signal_name = 'display_image',
                                       arg = self.imgDisplay )

            self.emit_fps_info()



            # Record video
            if self.recording:
                self.writer.write(self.imgDisplay)



            # Time the loop
            while (time.clock() - t0) < (1./self.fps):
                # Sleeping for < 15 ms is not reliable across different platforms.
                # Windows PCs generally have a minimum sleeping time > ~15 ms...
                #     making this timer exceeding the specified period.
                time.sleep(0.001)

            t0 = time.clock()

        # Disconnect signals from the gui object when the thread is done
        self.__init__signals(connect=False)

    def compute_depth(self, imgR, imgL):
        # Convert to gray scale
        imgR_ = cv2.cvtColor(imgR, cv2.COLOR_BGR2GRAY)
        imgL_ = cv2.cvtColor(imgL, cv2.COLOR_BGR2GRAY)

        # Compute stereo disparity
        stereo = cv2.StereoBM(cv2.STEREO_BM_BASIC_PRESET, self.ndisparities, self.SADWindowSize)
        D = stereo.compute(imgL_, imgR_).astype(np.float)
        depth_map = ( D - np.min(D) ) / ( np.max(D) - np.min(D) ) * 255

        for ch in xrange(3):
            imgL[:, :, ch] = depth_map.astype(np.uint8)

        return imgL

    def emit_fps_info(self):
        '''
        Emits real-time frame-rate info to the gui
        '''

        # Shift time series by one
        self.t_series[1:] = self.t_series[:-1]

        # Get the current time -> First in the series
        self.t_series[0] = time.time()

        # Calculate frame rate
        rate = len(self.t_series) / (self.t_series[0] - self.t_series[-1])

        text = 'Frame rate = {} fps'.format(rate)

        self.mediator.emit_signal( signal_name = 'set_info_text',
                                   arg = text )

    # Methods commanded by the high-level core object.

    def set_offset(self, offset_x, offset_y):

        x_limit, y_limit = 100, 100

        if abs(offset_x) > x_limit or abs(offset_y) > y_limit:
            self.offset_x, self.offset_y = 0, 0

        else:
            self.offset_x, self.offset_y = offset_x, offset_y

        self.set_resize_matrix()

    def detect_offset(self):
        '''
        1) Read right and left images from the cameras.
        2) Use correlation function to calculate the offset.
        '''

        imgR = self.capture_thread_R.get_image()
        imgL = self.capture_thread_L.get_image()

        imgR = cv2.cvtColor(imgR, cv2.COLOR_BGR2GRAY)
        imgL = cv2.cvtColor(imgL, cv2.COLOR_BGR2GRAY)

        if not imgR.shape == imgL.shape:
            return

        # Define ROI of the left image
        row, col = imgL.shape
        a = int(row*0.25)
        b = int(row*0.75)
        c = int(col*0.25)
        d = int(col*0.75)
        roiL = np.float32( imgL[a:b, c:d] )

        mat = cv2.matchTemplate(image  = np.float32(imgR)   ,
                                templ  = roiL               ,
                                method = cv2.TM_CCORR_NORMED)

        # Vertical alignment, should always be done
        y_max = cv2.minMaxLoc(mat)[3][1]
        offset_y = y_max - row / 4

        # Horizontal alignment, for infinitely far objects
        x_max = cv2.minMaxLoc(mat)[3][0]
        offset_x = x_max - col / 4

        return offset_x, offset_y

    def toggle_recording(self):

        self.temp_video_fname = 'temp.avi'

        if not self.recording:
            # Define the codec, which is platform specific and can be hard to find
            # Set fourcc = -1 so that can select from the available codec
            fourcc = -1

            # Some of the available codecs on native Windows PC: 'DIB ', 'I420', 'IYUV'...
            #     which are all uncompressive codecs
            # The compressive X264 codec needs to be installed seperately before use
            fourcc = cv2.cv.CV_FOURCC(*'X264')

            # Create VideoWriter object at 30fps
            w, h = self.display_width, self.display_height
            self.writer = cv2.VideoWriter(self.temp_video_fname, fourcc, self.fps, (w, h))

            if self.writer.isOpened():
                self.recording = True
                # Change the icon of the gui button
                self.mediator.emit_signal('recording_starts')
            else:
                print 'Video writer could not be opened.'

        else:
            self.recording = False
            self.writer.release()

            # Signal gui to change the icon of the button...
            #     and let the user to rename the temp file
            self.mediator.emit_signal('recording_ends', arg=self.temp_video_fname)

    def zoom_in(self):
        if self.zoom * 1.01 < 2.0:
            self.zoom = self.zoom * 1.01
            self.set_resize_matrix()

    def zoom_out(self):
        if self.zoom / 1.01 > 0.5:
            self.zoom = self.zoom / 1.01
            self.set_resize_matrix()

    def pause(self):
        self.pausing = True
        # Wait until the main loop is really paused before completing this method call
        while not self.isPaused:
            time.sleep(0.1)
        return

    def resume(self):
        self.pausing = False
        # Wait until the main loop is really resumed before completing this method call
        while self.isPaused:
            time.sleep(0.1)
        return

    def stop(self):
        'Called to terminate the video thread.'

        # Stop recording
        if self.recording:
            self.recording = False
            self.writer.release()

            # Remove the temporary video file as the recording is not properly stopped.
            os.remove(self.temp_video_fname)

        # Shut off main loop in self.run()
        self.stopping = True

    def apply_depth_parameters(self, parameters):

        for key, value in parameters.items():
            setattr(self, key, value)

    def set_display_size(self, width, height):
        self.pause()

        self.display_width, self.display_height = width, height
        self.set_resize_matrix()

        self.resume()

    def get_processed_images(self):
        return self.imgR_proc, self.imgL_proc

