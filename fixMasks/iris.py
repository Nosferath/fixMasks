from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat


_LEFT_OSIRIS_DATASET = 'left_480x80'
_RIGHT_OSIRIS_DATASET = 'right_480x80'
_OSIRIS_SHAPE = (80, 480)
_CHECK_MASKS_CSV = 'check_masks_full.csv'
_MASKS_FILE = 'new_masks.npz'


def load_raw_dataset(dataset_name: str):
    """This function loads a full dataset from a .mat file."""
    root_folder = Path('../data')
    data_mat = loadmat(str(root_folder / (dataset_name + '.mat')))
    data_array = data_mat['dataArray']
    label_array = data_mat['labelArray']
    mask_array = data_mat['maskArray']
    images_list = data_mat['imagesList']
    images_list = [
        images_list[i, 0][0][0] for i in range(images_list.shape[0])]
    images_list = list(map(lambda x: x.split('_')[0], images_list))
    return {
        'x': data_array,
        'y': label_array,
        'masks': mask_array,
        'list': np.array(images_list)
    }


class IrisImage:
    def __init__(self, data: np.ndarray, mask: np.ndarray,
                 shape=_OSIRIS_SHAPE + (1,)):
        """Class for managing the iris and its mask. Includes undo and
        redo actions."""
        self.data = data
        self.mask = mask
        self.shape = shape
        self.undo_stack = []
        self.redo_stack = []

    def get_visualization(self):
        """Visualizes the mask on the iris image. Allows certain
        transparency so the iris can still be seen."""
        visualization = self.data.reshape(self.shape)
        visualization = np.tile(visualization, [1, 1, 3])
        mask = self.mask.reshape(self.shape[:2])
        # Keep part of the base for visualization
        visualization[mask == 1, 1] = 255  # Instead of [0, 255, 0]
        return visualization

    def create_circular_mask(self, center, radius) -> np.ndarray:
        """Generates a circular mask. Used for drawing on masks.
        Center is (y,x)."""
        h, w = self.shape[:2]
        y, x = np.ogrid[:h, :w]
        dist_from_center: np.ndarray = np.sqrt(
            (y - center[0])**2 + (x - center[1])**2)
        mask = dist_from_center <= radius
        return mask

    def _base_draw_on_mask(self, coords, radius, value):
        """Applies the specified value onto a circular area in the mask.
        The area is defined by (y,x) coords of the center, and the
        radius of the circle."""
        self.undo_stack.append(self.mask.copy())
        self.redo_stack = []
        draw_mask = self.create_circular_mask(coords, radius)
        self.mask[draw_mask.flatten()] = value

    def draw_on_mask(self, coords, radius):
        """Draws a circle of the specified radius on the provided (y,x)
        coordinates."""
        self._base_draw_on_mask(coords, radius, 1)

    def erase_on_mask(self, coords, radius):
        """Deletes a circle of the specified radius on the provided
        (y,x) coordinates."""
        self._base_draw_on_mask(coords, radius, 0)

    def undo(self):
        """Restores the mask to its previous state."""
        if self.undo_stack:
            self.redo_stack.append(self.mask.copy())
            self.mask = self.undo_stack.pop()

    def redo(self):
        """Reverts an undo action."""
        if self.redo_stack:
            self.undo_stack.append(self.mask.copy())
            self.mask = self.redo_stack.pop()


class IrisDataset:
    def __init__(self):
        """Load and handle the dataset."""
        # Must always know which image is the current one, with its
        # latest state
        self.df = pd.read_csv(_CHECK_MASKS_CSV, index_col=0)
        self.n_images = len(self.df)
        self.data = {
            'left': load_raw_dataset(_LEFT_OSIRIS_DATASET),
            'right': load_raw_dataset(_RIGHT_OSIRIS_DATASET)
        }
        if not Path(_MASKS_FILE).exists():
            self.masks = np.zeros((self.n_images, np.prod(_OSIRIS_SHAPE)))
        else:
            self.masks = np.load(_MASKS_FILE)
        self.cur = None
        for i in range(self.n_images):
            if not self.df.checked.iloc[i]:
                # Index is set -1, so next image is the right one
                self.cur = i - 1
                break
        self.irisimage = None

    def get_irisimage(self):
        """Generates and returns the current Iris Image. Usually called
        from next()."""
        row = self.df.iloc[self.cur]
        key = row.dataset
        index = self.data[key]['list'] == row.filename
        data = self.data[key]['x'][index, :]
        # Load mask if it has been previously checked or modified
        if np.sum(self.masks[self.cur, :]) or self.df.checked.iloc[self.cur]:
            mask = self.masks[self.cur, :]
        else:
            mask = self.data[key]['masks'][index, :]
        self.irisimage = IrisImage(data, mask)
        return self.irisimage

    def save(self):
        """Saves the current mask into the mask array, and saves the
        array to its file. Also, sets current mask as checked."""
        if self.irisimage is None:
            raise ValueError('There is no current Iris Image')
        self.masks[self.cur, :] = self.irisimage.mask
        np.save(_MASKS_FILE, self.masks)

        self.df.checked.iloc[self.cur] = True
        self.df.to_csv(_CHECK_MASKS_CSV)

    def next(self, skip: list = None):
        """Returns the next Iris Image. If a skip list is supplied,
        images with a score that is on the list will be skipped"""
        self.cur += 1
        if skip is not None:
            while self.df.score.iloc[self.cur] in skip:
                self.cur += 1

        return self.get_irisimage()