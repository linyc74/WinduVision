'''
--- This is version 7.1 ---

    Introduced automatic camera tuning.

    In this first version for camera tuning,
        adjust left camera gain to equalize brightness levels in both images.

    Create a CamEqualThread class which operates via the VideoThread object:
        (1) Access and analyze images
        (2) Control camera gains



--- Version 7.0 ---

    Major change from 6.4 to 7.0:
        Split one set of camera parameters into two sets for right and left cameras, respective.
        This entails an extensive change of code strucutures and interfaces.
        Conceptually, everything involving camera parameters (get, set, read, write) is duplicated.
        The GUI window for setting camera parameters is also duplicated.

    Here I list the most notable changes:

    (1) Data structure of the 'cam.json' file, i.e. the camera parameters:
        {'R': {dictionary of parameters}, 'L': {dictionary of parameters}}

    (2) Extensive changes in the CameraTunerWindow class to account for right or left.

    (3) Instantiate two camera tuner windows, for R and L, respectively, in the main WinduGUI object.
        Related methods like open_camera_tuner() is also modified.

    (4) The data transferred from a CameraTunerWindow object to the WinduCore object is changed to the structure of
        {'isRightCam': True/False, 'parameters': {dictionary of parameters}}.

    (5) Changes in the apply_camera_parameters() methods in WinduCore, VideoThread classes.

    (6) Extensive changes in the DualCamera class.
        DualCamera class is a low-leveled class that directly operates camera hardwares (VideoCapture objects).
        The two VideoCapture objects are configured separately.



--- Version 6.4 ---

    Abandone the auto_offset() method, which aligns the left image to the right image for only one shot.

    For GUI control, replace the auto_offset() method with toggle_auto_offset().
    This toggling method pauses/resumes the loop in the AlignThread.
    Therefore users can turn ON or OFF the continuous alignment function.

    The main loop in the AlignThread was modified for pausing/resuming.

    The GUI icons for the toggle_auto_offset() method was also changed.
    Users can see the status, either ON or OFF, of auto offset.



--- Version 6.3 ---

    Major changes has been done in the AlignThread class,
    to resolve the problem of "jumping" image when there is a active and quick movement under the microscope.

    This jumping problem is possibly caused by asynchronous imaging of the two cameras, and
    can be considered as an outlier of alignment offset.

    Approaches to resolve the jumpiness:

        (1) Construct a queue of the past 10 offset values.
            Sort them, take out the highest and the lowest values.
            Average the median values.

        (2) Use the averaged values to set image offset.

        (3) If the current offset value differs significantly from the average, meaning that there is more "active movements",
            then speed up the loop to get back to a stable condition as soon as possible.



--- Version 6.2 ---

    Restructured the image processing pipeline in the video_thread object, with a few major points:

        (1) Combine the offset matrix and resize matrix into one single transformation matrix.

            This makes the image processing more efficient because the offset operation is
            combined into the resize operation.

            For mathematical details see 'transformation_matrix.docx'.

        (2) Factor out the depth computation into a separate method.

            Depth computation is done on the scaled images.



--- Version 6.1 ---

    Auto offset is executed upon inititating the software,
    which includes both vertical and horizontal offsets.

    There is a concurrent thread 'align_thread' running with the video_thread.
    The align_thread executes ONLY the vertical alignment every ~1 second.
    The horizontal offset should NOT be changed frequently to avoid visual discomfort.

'''

if __name__ == '__main__':
    from WinduModel import *
    app = QtGui.QApplication(sys.argv)
    core = WinduCore()
    sys.exit(app.exec_())
