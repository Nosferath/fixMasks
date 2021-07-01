import io

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
        nav_column = [[sg.B('Previous'), sg.B('Next')],
                      [sg.B('Save', s=(12, 1))],
                      [sg.Checkbox('Autosave', key='-AUTO-',
                                   tooltip='Save all changes to mask array '
                                           '(does not save to disk)')]]
        orig_column = [[sg.Image(key='-ORIGINAL-')]]
        layout = [[sg.T('Current image: None', s=(30, 1), key='-NAME-'),
                   CheckedText()],
                  [sg.Graph((960, 160), (0, 80), (480, 0), drag_submits=True,
                            enable_events=True, key='-IMAGE-')],
                  [sg.Frame('Draw tools', draw_column, vertical_alignment='t'),
                   sg.Column(nav_column, vertical_alignment='t'),
                   sg.Column(orig_column)]]
        self.window = sg.Window('Mask Fixer', layout=layout,
                                finalize=True)
        # TODO options for skipping images
        # TODO autosave box
        self.next()  # To initialize dataset and image

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
        self.window['-NAME-'].update('Current image: ' + str(self.image.name))
        self.window['-CHECKED-'].set_checked(self.dataset.is_image_checked())
        # Set original image
        data = image_to_bytes(self.dataset.get_original_image())
        self.window['-ORIGINAL-'].update(data=data)

    def next(self, skip: list = None):
        self.image = self.dataset.next(skip)
        self.update_image()

    def previous(self, skip: list = None):
        self.image = self.dataset.previous(skip)
        self.update_image()

    def update_alpha(self, value):
        self.alpha = value
        self.update_image()

    def check_status(self, scores: list = None):
        return self.dataset.check_status()

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

    def reset_mask(self):
        """Resets the current mask to its original state."""
        self.dataset.reset_mask()
        self.update_image()

    def save(self):
        """Saves the status of the masks to disk."""
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
        elif event in ('Draw', 'Erase'):
            gui.toggle_mode()
        elif event == 'Undo':
            gui.undo()
        elif event == 'Redo':
            gui.redo()
        elif event == 'Reset':
            gui.reset_mask()
        elif event == '-ALPHA-':  # Mask alpha slider
            gui.update_alpha(values['-ALPHA-'])
        # Nav column
        elif event == 'Previous':
            gui.previous()
        elif event == 'Next':
            gui.next()
        elif event == 'Save':
            gui.save()
        # Image
        elif event == '-IMAGE-':
            gui.click_image(values['-IMAGE-'])
        elif event == '-IMAGE-+UP':
            gui.mouse_up()

        # TODO mouse wheel for size
        # TODO right click for swapping draw/erase
        # TODO measure time per image

        if gui.check_status():
            # TODO What to do if all images have been checked
            pass
    gui.window.close()


if __name__ == '__main__':
    main()
