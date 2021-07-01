import io
import tracemalloc

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


class GUI:
    def __init__(self, dataset: IrisDataset):
        self.dataset = dataset
        self.image = None
        self.drawn_image = None
        self.layout = [[sg.Text('Image name', key='name')],
                       [sg.Graph((960, 160), (0, 80), (480, 0), background_color='white',
                                 drag_submits=True, enable_events=True,
                                 key='image')],
                       [sg.Button('Draw', disabled=True), sg.Button('Erase'),
                        sg.Button('Undo'), sg.Button('Redo'),
                        sg.Button('Previous'), sg.Button('Next')],
                       [sg.Slider((0.0, 1.0), default_value=0.5,
                                  resolution=0.1, orientation='h',
                                  enable_events=True, key='alpha')]]
        # TODO Buttons for draw size and mode (draw/erase)
        self.window = sg.Window('Mask Fixer', layout=self.layout,
                                finalize=True)
        self.alpha = 0.5  # Alpha value for visualization
        self.next()  # To initialize dataset and image
        self.draw_mode = True
        self.radius = 4
        self.next_draw_saves = True  # False when in the middle of a drawing

    def update_image(self):
        if self.drawn_image is not None:
            self.window['image'].delete_figure(self.drawn_image)
        image = self.image.get_visualization(self.alpha)
        image = Image.fromarray(image).resize((960, 160), Image.NEAREST)
        with io.BytesIO() as output:
            image.save(output, format='PPM')
            data = output.getvalue()
        self.drawn_image = self.window['image'].draw_image(data=data,
                                                           location=(0, 0))
        # print(self.drawn_image)
        self.window['name'].update(self.image.name)

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
        if self.next_draw_saves:
            self.next_draw_saves = False
            self.image.save_state()
        if self.draw_mode:
            self.image.draw_on_mask((coords[1], coords[0]), self.radius)
        else:
            self.image.erase_on_mask((coords[1], coords[0]), self.radius)
        self.update_image()

    def mouse_up(self):
        """Release the mouse button, which means a drawing ended."""
        self.next_draw_saves = True


def main():
    gui = GUI(IrisDataset())
    while True:
        event, values = gui.window.read(timeout=0)
        if event == sg.WIN_CLOSED:
            break
        elif event in ('Draw', 'Erase'):
            gui.toggle_mode()
        elif event == 'Next':
            gui.next()
        elif event == 'Previous':
            gui.previous()
        elif event == 'Undo':
            gui.undo()
        elif event == 'Redo':
            gui.redo()
        elif event == 'alpha':  # Mask alpha slider
            gui.update_alpha(values['alpha'])
        elif event == 'image':
            gui.click_image(values['image'])
        elif event == 'image+UP':
            gui.mouse_up()

        # TODO Buttons for draw size
        # TODO mouse wheel for size
        # TODO right click for swapping draw/erase
        # TODO measure time per image

        if gui.check_status():
            # TODO What to do if all images have been checked
            pass
    gui.window.close()


if __name__ == '__main__':
    tracemalloc.start()
    main()
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    print("[ Top 10 ]")
    for stat in top_stats[:10]:
        print(stat)
