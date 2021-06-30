# import cv2
# from PIL import Image
import PySimpleGUI as sg

from iris import IrisImage


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
    def __init__(self):
        self.image = None
        self.layout = [[sg.Text('Image name', key='name')],
                       [sg.Image(data=None, key='image')]]
        self.window = sg.Window('Mask Fixer', layout=self.layout)

        # TODO click-mask interaction
        # TODO Buttons for draw size and mode (draw/erase)


def main():
    gui = GUI()
    while True:
        event, values = gui.window.read()
        if event == sg.WIN_CLOSED:
            break
    gui.window.close()


if __name__ == '__main__':
    main()
