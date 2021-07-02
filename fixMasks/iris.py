from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat


_LEFT_OSIRIS_DATASET = 'left_480x80'
_RIGHT_OSIRIS_DATASET = 'right_480x80'
_OSIRIS_SHAPE = (80, 480)
_CHECK_MASKS_CSV = 'check_masks_full.csv'
_MASKS_FILE = 'new_masks.npz'
_ORIGINAL_LEFT_PATH = Path('S:/NUND_left/')
_ORIGINAL_RIGHT_PATH = Path('S:/NUND_right/')


def load_raw_dataset(dataset_name: str):
    """This function loads a full dataset from a .mat file."""
    root_folder = Path('../data')
    data_mat = loadmat(str(root_folder / (dataset_name + '.mat')))
    data_array = data_mat['dataArray']
    label_array = data_mat['labelArray']
    mask_array = data_mat['maskArray']
    images_list = data_mat['imagesList']
    images_list = [
        images_list[i, 0][0][0] for i in range(images_list.shape[0])
    ]
    images_list = np.array(list(map(lambda x: x.split('_')[0], images_list)))
    data_array.flags.writeable = False
    label_array.flags.writeable = False
    mask_array.flags.writeable = False
    images_list.flags.writeable = False
    return {
        'x': data_array,
        'y': label_array,
        'masks': mask_array,
        'list': images_list
    }


class IrisImage:
    def __init__(self, data: np.ndarray, mask: np.ndarray,
                 shape=_OSIRIS_SHAPE + (1,), name='', score=None,
                 max_queue=20):
        """Class for managing the iris and its mask. Includes undo and
        redo actions.
        """
        if len(data.shape) == 2:
            self.data = data[0, :]
        else:
            self.data = data
        self.mask = None
        self.set_mask(mask)
        self.shape = shape
        self.undo_stack = []
        self.redo_stack = []
        self.name = name
        self.score = score
        self._max_queue = max_queue

    def get_visualization(self, alpha=0.5):
        """Visualizes the mask on the iris image. Alpha sets the
        transparency of the mask, with 1 being solid and 0 being
        invisible.
        """
        visualization = self.data.reshape(self.shape)
        visualization = np.tile(visualization, [1, 1, 3])
        mask = self.mask.reshape(self.shape[:2])
        # Keep part of the base for visualization
        base_values = visualization[mask == 1, :]
        mask_values = np.tile([[0, 255, 0]], (base_values.shape[0], 1))
        visualization[mask == 1, :] = ((1 - alpha)*base_values
                                       + alpha*mask_values)
        return visualization

    def create_circular_mask(self, center, radius) -> np.ndarray:
        """Generates a circular mask. Used for drawing on masks.
        Center is (y,x).
        """
        h, w = self.shape[:2]
        y, x = np.ogrid[:h, :w]
        dist_from_center: np.ndarray = np.sqrt(
            (y - center[0])**2 + (x - center[1])**2)
        mask = dist_from_center <= radius
        return mask

    def _base_draw_on_mask(self, coords, radius, value):
        """Applies the specified value onto a circular area in the mask.
        The area is defined by (y,x) coords of the center, and the
        radius of the circle.
        """
        draw_mask = self.create_circular_mask(coords, radius)
        self.mask[draw_mask.flatten()] = value

    def draw_on_mask(self, coords, radius):
        """Draws a circle of the specified radius on the provided (y,x)
        coordinates.
        """
        self._base_draw_on_mask(coords, radius, 1)

    def erase_on_mask(self, coords, radius):
        """Deletes a circle of the specified radius on the provided
        (y,x) coordinates.
        """
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

    def save_state(self):
        """Used when starting a new drawing to save the current mask
        state for the undo stack.
        """
        self.undo_stack.append(self.mask.copy())
        if len(self.undo_stack) > self._max_queue:
            del self.undo_stack[0]
        self.redo_stack = []

    def set_mask(self, mask):
        if len(mask.shape) == 2:
            self.mask = mask[0, :]
        else:
            self.mask = mask


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
            self.masks = np.load(_MASKS_FILE)['masks']
        self.cur = None
        for i in range(self.n_images):
            if not self.df.checked.loc[i]:
                # Index is set -1, so next image is the right one
                self.cur = i
                break
        self._first = True  # Next image will be the first since init
        self.irisimage = None

    def check_status(self, scores: list = None):
        """Returns True if all images have been checked, or False other-
        wise. If a scores list is supplied, this will only check if
        irises with these scores have been checked.
        """
        if scores is None:
            to_check = self.df
        else:
            to_check = self.df[self.df.score.isin(scores)]
        return to_check.checked.all()

    def is_image_checked(self):
        """Returns whether the current Iris Image has been checked."""
        return self.df.loc[self.cur, 'checked']

    def get_irisimage(self):
        """Generates and returns the current Iris Image. Usually called
        from next() or previous().
        """
        row = self.df.loc[self.cur]
        key = row.dataset
        index = self.data[key]['list'] == row.filename
        data = self.data[key]['x'][index, :]
        # Load mask if it has been previously checked or modified
        if np.sum(self.masks[self.cur, :]) or self.df.checked.loc[self.cur]:
            mask = self.masks[self.cur, :].copy()
        else:
            mask = self.data[key]['masks'][index, :].copy()
        self.irisimage = IrisImage(data, mask, name=row.filename,
                                   score=row.score)

        return self.irisimage

    def save(self, checked=True, to_disk=True):
        """Saves the current mask into the mask array. If checked is
        true, sets the current mask as checked in the DF. If to_disk is
        True, saves the mask array and DF to their corresponding files.
        """
        if self.irisimage is None:
            raise ValueError('There is no current Iris Image')
        self.masks[self.cur, :] = self.irisimage.mask.copy()
        if checked:
            self.df.loc[self.cur, 'checked'] = True
        if to_disk:
            np.savez_compressed(_MASKS_FILE, masks=self.masks)
            self.df.to_csv(_CHECK_MASKS_CSV)

    def next(self, skip: list = None):
        """Returns the next Iris Image. If a skip list is supplied,
        images with a score that is on the list will be skipped.
        """
        if self._first:
            self._first = False
            return self.get_irisimage()
        self.cur = (self.cur + 1) % self.n_images
        if skip is not None:
            while self.df.score.loc[self.cur] in skip:
                self.cur = (self.cur + 1) % self.n_images

        return self.get_irisimage()

    def previous(self, skip: list = None):
        """Returns the previous Iris Image. If a skip list is supplied,
        images with a score that is on the list will be skipped.
        """
        if self._first:
            self._first = False
            return self.get_irisimage()
        self.cur = (self.cur - 1) % self.n_images
        if skip is not None:
            while self.df.score.loc[self.cur] in skip:
                self.cur = (self.cur - 1) % self.n_images

        return self.get_irisimage()

    def reset_mask(self):
        """Resets the current mask to its original state.
        Triggers save_state.
        """
        self.irisimage.save_state()
        row = self.df.loc[self.cur]
        key = row.dataset
        index = self.data[key]['list'] == row.filename
        mask = self.data[key]['masks'][index, :]
        self.irisimage.set_mask(mask)

    def get_original_image(self):
        """Returns a PIL image containing the original not-normalized
        iris image.
        """
        row = self.df.loc[self.cur]
        if row.dataset == 'left':
            path = _ORIGINAL_LEFT_PATH
        else:
            path = _ORIGINAL_RIGHT_PATH
        filename = row.filename + '.tiff'
        return Image.open(path / filename)

    def get_cur_position(self):
        return '{:04n}/{}'.format(self.cur + 1, self.n_images)
