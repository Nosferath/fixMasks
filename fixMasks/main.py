import io
import time

# import cv2
import numpy as np
from PIL import Image
import PySimpleGUI as sg

from iris import IrisDataset, IrisImage


# class TempImage:
#     def __init__(self, filename='temp'):
#         self.iris = None
#         self.filename = filename
#         if not self.filename.endswith('.png'):
#             self.filename += '.png'
#
#     def set_iris(self, iris: IrisImage):
#         self.iris = iris
#
#     def update(self):
#         if self.iris is None:
#             img = np.zeros((80, 480, 3))
#         else:
#             img = self.iris.get_visualization()
#         return img.tobytes()

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

    @staticmethod
    def _format_time(seconds):
        """Returns the time formatted as hh:mm:ss"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = int(seconds % 60)
        return '{:02n}:{:02n}:{:02n}'.format(hours, minutes, seconds)

    def get_average(self):
        """Returns the average of all times, formatted."""
        if len(self._times):
            return self._format_time(np.mean(self._times))
        return self._format_time(0)

    def get_current(self):
        """Returns the current elapsed time, formatted."""
        if self._start_t is not None:
            return self._format_time(time.time() - self._start_t)
        return self._format_time(0)

    def get_all(self):
        """Returns a list with all times, formatted."""
        if len(self._times):
            return [self._format_time(s) for s in self._times]
        return [self._format_time(0)]


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
        draw_column = [[sg.T('Radius:'), sg.Spin(
            list(range(1, 11)), 5, readonly=True, key='-RADIUS-'
                        ), sg.B('Draw', disabled=True), sg.B('Erase')],
                       [sg.B('Undo'), sg.B('Redo'), sg.B('Reset')],
                       [sg.T('Mask opacity:')],
                       [sg.Slider((0.0, 1.0), default_value=0.5,
                                  resolution=0.1, orientation='h',
                                  enable_events=True, key='-ALPHA-')]]
        nav_column1 = [[sg.B('Previous'), sg.B('Next')],
                       [sg.B('Save', s=(12, 1))],
                       [sg.Checkbox('Autosave', default=True, key='-AUTO-',
                                    tooltip='Save all changes to mask array '
                                            '(does not save to disk)')]]
        nav_column2 = [[sg.Checkbox('0', key='-SKIP0-'),
                        sg.Checkbox('1', key='-SKIP1-'),
                        sg.Checkbox('2', key='-SKIP2-')]]
        nav_column = [*nav_column1,
                      [sg.Frame('Skip options', nav_column2)]]
        orig_column = [[sg.Image(key='-ORIGINAL-')]]
        layout = [[sg.T('Current image: None. Score: None.', s=(35, 1),
                        key='-NAME-'),
                   CheckedText()],
                  [sg.Graph((960, 160), (0, 80), (480, 0), drag_submits=True,
                            enable_events=True, key='-IMAGE-')],
                  [sg.Frame('Draw tools', draw_column, vertical_alignment='t'),
                   sg.Column(nav_column, vertical_alignment='t'),
                   sg.Column(orig_column)]]
        self.window = sg.Window('Mask Fixer', layout=layout,
                                finalize=True, return_keyboard_events=True)
        # Set mouse bindings
        self.window['-IMAGE-'].bind('<Button-3>', '+RIGHT')
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
        self.window['-NAME-'].update('Current image: ' + self.image.name
                                     + '. Score: ' + str(self.image.score))
        self.window['-CHECKED-'].set_checked(self.dataset.is_image_checked())
        # Set original image
        data = image_to_bytes(self.dataset.get_original_image())
        self.window['-ORIGINAL-'].update(data=data)

    def get_skips(self):
        d = {'-SKIP0-': 0, '-SKIP1-': 1, '-SKIP2-': 2}
        skip = []
        for key, value in d.items():
            if self.window[key].get():
                skip.append(d[key])
        if len(skip) == 3:
            print('[WARNING] Cannot skip all values. Treating as None.')
            skip = []
        return skip

    def next(self):
        skip = self.get_skips()
        self.image = self.dataset.next(skip)
        self.update_image()

    def previous(self):
        skip = self.get_skips()
        self.image = self.dataset.previous(skip)
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

    def save(self):
        """(On button click) Saves the status of the masks to disk."""
        if not self.debug_mode:
            self.dataset.save()
        else:
            self.dataset.save(to_disk=False)
            print('[DEBUG] Save triggered.')
        self.update_image()


def main():
    gui = GUI(IrisDataset())
    while True:
        event, values = gui.window.read()
        if event == sg.WIN_CLOSED:
            break
        # Draw column
        elif event in ('Draw', 'Erase', '-IMAGE-+RIGHT'):
            gui.toggle_mode()
        elif event in ('Undo', 'z:90'):
            gui.undo()
        elif event in ('Redo', 'y:89'):
            gui.redo()
        elif event == 'Reset':
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
        # Image
        elif event == '-IMAGE-':
            gui.click_image(values['-IMAGE-'])
        elif event == '-IMAGE-+UP':
            gui.mouse_up()
        else:
            if gui.debug_mode:
                print(event)
        # TODO measure time per image

        if gui.check_status():
            # TODO What to do if all images have been checked
            pass
    gui.window.close()


if __name__ == '__main__':
    main()
