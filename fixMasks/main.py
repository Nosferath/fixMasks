import io
import time

# import cv2
import numpy as np
from PIL import Image
import PySimpleGUI as sg

from iris import IrisDataset, IrisImage


def image_to_bytes(image):
    """Converts a PIL image to bytes."""
    with io.BytesIO() as output:
        if image.mode != 'P':
            image.save(output, format='PPM')
        else:
            image.save(output, format='PNG')
        data = output.getvalue()
    return data


class Timer:
    def __init__(self):
        """Timer and tracker of previous times. Includes multiple
        functions for getting statistics about the tracked times."""
        self._times = []
        self._start_t = None

    def start(self):
        """Starts a timer if it hasn't been started already. Otherwise
        it does nothing (allowing for this to be called safely).
        """
        if self._start_t is None:
            self._start_t = time.time()

    def stop(self):
        """Stops a timer if it has been started. Otherwise it does
        nothing (allowing for this to be called safely).
        """
        if self._start_t is not None:
            self._times.append(time.time() - self._start_t)
            self._start_t = None

    def reset(self):
        """Deletes all previous times, resetting the timer."""
        self._times = []
        self._start_t = None

    @staticmethod
    def _format_time(seconds) -> str:
        """Returns the time formatted as hh:mm:ss"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = int(seconds % 60)
        return '{:02n}:{:02n}:{:02n}'.format(hours, minutes, seconds)

    def get_average(self) -> str:
        """Returns the average of all times, formatted."""
        if self._times:
            return self._format_time(np.mean(self._times))
        return self._format_time(0)

    def get_current(self) -> str:
        """Returns the current elapsed time, formatted."""
        if self._start_t is not None:
            return self._format_time(time.time() - self._start_t)
        return self._format_time(0)

    def get_all(self):
        """Returns a list with all times, formatted."""
        return [self._format_time(s) for s in self._times]

    def has_started(self) -> bool:
        """Return True if the timer has been started"""
        return self._start_t is not None

    def get_eta(self, n: int):
        """Get ETA for n images, based on average time."""
        if self._times:
            return self._format_time(np.mean(self._times) * n)
        return self._format_time(0)

    def remove_last(self):
        """Remove the last recorded time."""
        self._times.pop()


class CheckedText(sg.T):
    def __init__(self):
        super().__init__('NOT CHECKED', s=(15, 1), text_color='red',
                         key='-CHECKED-')
        self.checked = False

    def set_checked(self, checked):
        self.checked = checked
        if self.checked:
            super().update('CHECKED', text_color='#00FF00')
        else:
            super().update('NOT CHECKED', text_color='red')


class GUI:
    def __init__(self, dataset: IrisDataset, debug_mode=True):
        self.dataset = dataset
        self.image = None
        self.drawn_image = None
        self.debug_mode = debug_mode
        self.alpha = 0.5  # Alpha value for visualization
        self.draw_mode = True
        self.next_draw_saves = True  # False when in the middle of a drawing
        self.timer = Timer()
        # Create layout
        timer_menu = [
            [sg.T('00:00:00', font=('Helvetica', 30), key='-TIME-')],
            [sg.T('Average time: 00:00:00', s=(20, 1), key='-AVG-')],
            [sg.T('ETA: 00:00:00', s=(20, 1), key='-ETA-')],
            [sg.B('Start', tooltip='Hotkey: s'),
             sg.B('Stop', tooltip='Hotkey: s'),
             sg.B('Reset', key='-RESETTIMER-'),
             sg.B('-', key='-REMOVELAST-')],
            [sg.Multiline('', s=(20, 13), write_only=True, key='-TIMELIST-')]
        ]
        draw_column = [
            [sg.T('Radius:'), sg.Spin(
                list(range(1, 11)), 5, readonly=True, key='-RADIUS-'
            ), sg.B('Draw', disabled=True), sg.B('Erase')],
            [sg.B('Undo'), sg.B('Redo'), sg.B('Reset', key='-RESETMASK-')],
            [sg.T('Mask opacity:')],
            [sg.Slider((0.0, 1.0), default_value=0.5, resolution=0.1,
                       orientation='h', enable_events=True, key='-ALPHA-')]
        ]
        nav_column1 = [
            [sg.B('Previous'), sg.B('Next')],
            [sg.B('Save', s=(12, 1))],
            [sg.Checkbox(
                'Autosave', default=True, key='-AUTO-',
                tooltip='Save all changes to mask array '
                        '(does not save to disk)'
            )],
            [sg.Checkbox('Checked', enable_events=True, key='-CHECKBOX-')]
        ]
        nav_column2 = [
            [sg.Checkbox('0', key='-SKIP0-'), sg.Checkbox('1', key='-SKIP1-'),
             sg.Checkbox('2', key='-SKIP2-')],
            [sg.Checkbox('Checked', key='-SKIPC-')]
        ]
        nav_column = [
            *nav_column1,
            [sg.Frame('Skip options', nav_column2)]
        ]
        orig_column = [
            [sg.Image(key='-ORIGINAL-')]
        ]
        layout = [
            [sg.T('Current image: None.\tScore: None.\t   0/0', s=(40, 1),
                  key='-NAME-'),
             CheckedText(), sg.T('{} remaining'.format(
                self.dataset.get_remaining_images()), key='-REMAINING-'),
             sg.T('', s=(20, 1), text_color='#00FF00', key='-FINISHED-')],
            [sg.Graph((960, 160), (0, 80), (480, 0), drag_submits=True,
                      enable_events=True, key='-IMAGE-')],
            [sg.Column(
                [[sg.Frame('Draw tools', draw_column, vertical_alignment='t'),
                  sg.Column(nav_column, vertical_alignment='t')],
                 [sg.Frame('Timer', timer_menu)]],
                element_justification='center'),
             sg.Column(orig_column)]
        ]
        self.window = sg.Window('Mask Fixer', layout=layout,
                                finalize=True, return_keyboard_events=True)
        # Set mouse bindings
        self.window['-IMAGE-'].bind('<Button-3>', '+RIGHT')
        # Wheel binding no longer needed
        # self.window['-IMAGE-'].bind('<MouseWheel>', '+WHEEL')
        # Initialize dataset and image
        self.next()

    def update_image(self):
        # if self.drawn_image is not None:
        # Delete previous figure to prevent memory leak
        self.window['-IMAGE-'].delete_figure(self.drawn_image)
        # Convert image to Bytes64
        image = self.image.get_visualization(self.alpha)
        image = Image.fromarray(image).resize((960, 160), Image.NEAREST)
        data = image_to_bytes(image)
        # Set image and text
        self.drawn_image = self.window['-IMAGE-'].draw_image(
            data=data, location=(0, 0))
        self.window['-NAME-'].update(
            'Current image: ' + self.image.name
            + '\tScore: ' + str(self.image.score)
            + '\t   ' + self.dataset.get_cur_position()
        )
        self.window['-CHECKED-'].set_checked(self.dataset.is_image_checked())
        self.window['-CHECKBOX-'].update(self.dataset.is_image_checked())
        # Set original image
        data = image_to_bytes(self.dataset.get_original_image())
        self.window['-ORIGINAL-'].update(data=data)

    def get_skips(self):
        d = {'-SKIP0-': 0, '-SKIP1-': 1, '-SKIP2-': 2}
        skip = []
        for key, value in d.items():
            if self.window[key].get():
                skip.append(d[key])
        return skip

    def next(self):
        skip = self.get_skips()
        skip_checked = self.window['-SKIPC-'].get()
        self.image = self.dataset.next(skip, skip_checked)
        self.update_image()

    def previous(self):
        skip = self.get_skips()
        skip_checked = self.window['-SKIPC-'].get()
        self.image = self.dataset.previous(skip, skip_checked)
        self.update_image()

    def update_alpha(self, value):
        self.alpha = value
        self.update_image()

    def check_status(self, scores: list = None):
        return self.dataset.check_status(scores)

    def undo(self):
        self.image.undo()
        self.update_image()

    def redo(self):
        self.image.redo()
        self.update_image()

    def toggle_mode(self):
        self.draw_mode = not self.draw_mode
        if self.draw_mode:
            self.window['Draw'].update(disabled=True)
            self.window['Erase'].update(disabled=False)
        else:
            self.window['Draw'].update(disabled=False)
            self.window['Erase'].update(disabled=True)

    def click_image(self, coords):
        """Draw or erase on the mask. Coords are (x, y)."""
        radius = self.window['-RADIUS-'].get()
        if self.next_draw_saves:
            self.next_draw_saves = False
            self.image.save_state()
        if self.draw_mode:
            self.image.draw_on_mask((coords[1], coords[0]), radius)
        else:
            self.image.erase_on_mask((coords[1], coords[0]), radius)
        self.update_image()

    def mouse_up(self):
        """Release the mouse button, which means a drawing ended."""
        self.next_draw_saves = True
        if self.window['-AUTO-'].get():
            self.dataset.save(checked=False, to_disk=False)

    def wheel_radius(self, event):
        """Incr. or decr. drawing radius after a MouseWheel event."""
        radius = self.window['-RADIUS-'].get()
        if event.endswith(':Up'):
            self.window['-RADIUS-'].update(min(10, radius + 1))
        elif event.endswith(':Down'):
            self.window['-RADIUS-'].update(max(1, radius - 1))

    def reset_mask(self):
        """Resets the current mask to its original state."""
        self.dataset.reset_mask()
        self.update_image()

    def save(self, from_exit=False):
        """(On button click) Saves the status of the masks to disk."""
        if from_exit:
            self.dataset.save(checked=False, to_disk=True)
            return
        if not self.debug_mode:
            self.dataset.save()
        else:
            self.dataset.save(to_disk=False)
            print('[DEBUG] Save triggered.')
        self.update_image()
        # Update remaining images number
        self.window['-REMAINING-'].update('{} remaining'.format(
            self.dataset.get_remaining_images()))
        # Check and display if any image types are finished
        fnshd = [str(i) for i in range(3) if self.check_status([i])]
        if fnshd:
            self.window['-FINISHED-'].update('FINISHED: ' + ','.join(fnshd))

    def update_timer(self):
        """Updates the displayed timer when a timer has been started.
        Called in each window update.
        """
        if self.timer.has_started():
            self.window['-TIME-'].update(self.timer.get_current())

    def start_timer(self):
        """Starts the timer."""
        self.timer.start()

    def stop_timer(self):
        """Stops the timer and updates timer visualizations."""
        self.timer.stop()
        self.window['-TIME-'].update(self.timer.get_current())
        self.window['-TIMELIST-'].update('\n'.join(self.timer.get_all()))
        self.window['-AVG-'].update(
            'Average time: ' + self.timer.get_average())
        self.window['-ETA-'].update(
            'ETA: ' + self.timer.get_eta(self.dataset.get_remaining_images())
        )

    def reset_timer(self):
        """Resets the timer (and updates visualizations)."""
        self.timer.reset()
        self.stop_timer()  # For update

    def remove_last(self):
        """Removes the last recorded time (and updates visualizations).
        """
        self.timer.remove_last()
        self.stop_timer()

    def check_image(self):
        """Sets the image as checked or unchecked based on the checkbox
        status. Triggered by clicking the checkbox."""
        checked = self.window['-CHECKBOX-'].get()
        self.dataset.set_checked(checked)
        # Update remaining images number
        self.window['-REMAINING-'].update('{} remaining'.format(
            self.dataset.get_remaining_images()))

        self.update_image()


def main(debug):
    gui = GUI(IrisDataset(), debug_mode=debug)
    while True:
        event, values = gui.window.read(timeout=1000)
        gui.update_timer()
        if event == sg.WIN_CLOSED:
            gui.save(from_exit=True)
            break
        # Draw column
        elif event in ('Draw', 'Erase', '-IMAGE-+RIGHT'):
            gui.toggle_mode()
        elif event in ('Undo', 'z:90'):
            gui.undo()
        elif event in ('Redo', 'y:89'):
            gui.redo()
        elif event == '-RESETMASK-':
            gui.reset_mask()
        elif event == '-ALPHA-':  # Mask alpha slider
            gui.update_alpha(values['-ALPHA-'])
        elif event.startswith('MouseWheel'):
            gui.wheel_radius(event)
        # Nav column
        elif event in ('Previous', 'Left:37'):
            gui.previous()
        elif event in ('Next', 'Right:39'):
            gui.next()
        elif event == 'Save':
            gui.save()
        elif event == '-CHECKBOX-':
            gui.check_image()
        # Timer
        elif event == 'Start':
            gui.start_timer()
        elif event == 'Stop':
            gui.stop_timer()
        elif event == 's':
            if gui.timer.has_started():
                gui.stop_timer()
            else:
                gui.start_timer()
        elif event == '-RESETTIMER-':
            gui.reset_timer()
        elif event == '-REMOVELAST-':
            gui.remove_last()
        # Image
        elif event == '-IMAGE-':
            gui.click_image(values['-IMAGE-'])
        elif event == '-IMAGE-+UP':
            gui.mouse_up()
        elif event == '__TIMEOUT__':  # Supress prints
            pass
        else:
            if gui.debug_mode:
                print(event)
    gui.window.close()


if __name__ == '__main__':
    main(debug=False)
