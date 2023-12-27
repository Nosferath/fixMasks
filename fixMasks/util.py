from itertools import product
from os import chdir, getcwd
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat
from skimage.measure import block_reduce
from tqdm import trange

from .iris import load_raw_dataset, IrisImage


EYES = ('left', 'right')
# [0] must always be iris , [1] masks [2] visual(ization),
# [3] visual_old
SUBFOLDERS = ('iris', 'masks', 'visual', 'visual_old')


def ready_iris(input_iris: np.ndarray, to_size: tuple, from_size=(80, 480)):
    """Reshapes, [resizes] and converts iris to PIL.Image."""
    iris = input_iris.reshape(from_size)
    out_iris = Image.fromarray(iris)
    if to_size != from_size:
        out_iris = out_iris.resize(to_size[::-1])
    return out_iris


def resize_mask(input_mask: np.ndarray, to_size: tuple, from_size=(80, 480)):
    if to_size[0]*2 == from_size[0]:
        h = 2
    elif to_size[0]*4 == from_size[0]:
        h = 4
    else:
        raise ValueError('Vertical ratio not supported')
    if to_size[1]*2 == from_size[1]:
        w = 2
    elif to_size[1]*4 == from_size[1]:
        w = 4
    else:
        raise ValueError('Horizontal ratio not supported')

    out_mask = block_reduce(input_mask, (h, w), np.max)
    return out_mask.astype('uint8') * 255


def ready_mask(input_mask: np.ndarray, to_size: tuple, from_size=(80, 480)):
    """Reshapes and resizes input mask to the chosen size. If to_size is
    then same as the from_size, no resize takes place.
    Input mask must be a 1D binary vector
    (values 0 or 1).
    """
    mask = input_mask.reshape(from_size)
    if to_size == from_size:
        return mask.astype('uint8') * 255
    out_mask = resize_mask(mask, to_size, from_size)
    return out_mask


def generate_visualization(iris: np.ndarray, mask: np.ndarray, shape: tuple):
    """Generates a visualization of the masked iris."""
    iris_image = IrisImage(iris, mask, shape + (1,))
    return iris_image.get_visualization(1.0)


def export_masks_as_images(out_folder: str,
                           out_shapes: list,
                           npz_file='new_masks.npz',
                           csv_file='check_masks_full.csv',
                           orig_shape=(80, 480),
                           use_old_mask=False,
                           gen_old_visualization=False,
                           gen_new_visualization=False):
    """Exports the masks in the .npz file as images, together with the
    iris image. The name for each mask and their sub-folders are
    obtained from the .csv.

    Parameters
    ----------
    out_folder : str
        Root folder where the subfolders will be generated. Created if non-
        existent. The resulting structure will be as follows:
            out_folder/
            ├── left_[dataset]/
            │   ├── iris/
            │   │   ├── [filename].bmp
            │   │   └── ....
            │   └── masks/
            │       └── ....
            └── right_[dataset]/
                ├── iris/
                │   └── ....
                └── masks/
                    └── ....

    out_shapes : list or tuple of ints
        List of shapes of the image sizes to generate,
        in (width, height) format. From these the [dataset] will be
        generated.

    npz_file : str, optional
        Path of the .npz file containing the new masks array.

    csv_file : str, optional
        Path of the .csv file listing the images in the new masks array.

    orig_shape : tuple of int, optional
        Original shape of the masks in array, in (rows, cols) format.
    """
    old_dir = None
    if Path.cwd().name == 'fixMasks' and Path('fixMasks').exists():
        old_dir = getcwd()
        chdir('fixMasks')
    # Determine datasets from the original shape and out shapes
    orig_dataset = 'x'.join(str(i) for i in orig_shape[::-1])
    datasets = tuple('x'.join(str(i) for i in shape[::-1])
                     for shape in out_shapes)
    # Load data
    masks = np.load(npz_file)['masks']
    df = pd.read_csv(csv_file, index_col=0)
    n_masks = len(df)
    data_dict = {eye: load_raw_dataset(eye + '_' + orig_dataset)
                 for eye in ('left', 'right')}
    # _labels is for checking that the labels I have on MATLAB are the
    # same as the ones on labels.mat as well as on the dataset .mats
    _labels = loadmat('../data/labels.mat')['labels']  # DEBUG
    _labels = {i[0][0]: i[1][0][0] for i in _labels}  # DEBUG
    _diff_labels = 0  # DEBUG
    # Generate out folders
    out_folder = Path(out_folder)
    out_folder.mkdir(exist_ok=True, parents=True)
    for f, dataset in product(df.dataset.unique(), datasets):
        dataset_dir = out_folder / (f + '_' + dataset)
        dataset_dir.mkdir(exist_ok=True)
        for sf in SUBFOLDERS:
            sub_folder = dataset_dir / sf
            sub_folder.mkdir(exist_ok=True)
    # Generate images
    for shape_idx in range(len(out_shapes)):
        resize_shape = out_shapes[shape_idx]
        dataset = datasets[shape_idx]
        print('Generating ' + dataset + ' dataset.')
        for i in trange(n_masks, unit='masks'):
            # Initialize current
            row = df.loc[i]
            cur_dir = out_folder / (row.dataset + '_' + dataset)
            iris_dir = cur_dir / SUBFOLDERS[0]
            mask_dir = cur_dir / SUBFOLDERS[1]
            vis_dir = cur_dir / SUBFOLDERS[2]
            old_vis_dir = cur_dir / SUBFOLDERS[3]
            cur_name = row.filename + '.bmp'
            cur_mask = masks[i, :]
            cur_data_dict = data_dict[row.dataset]
            # Find current image on data
            idx = np.where(cur_data_dict['list'] == row.filename)[0]
            if not len(idx):
                print(f'[WARNING] {cur_name} not found.')
                continue
            iris = cur_data_dict['x'][idx[0], :]
            old_mask = cur_data_dict['masks'][idx[0], :]
            if use_old_mask:
                cur_mask = old_mask
            # Check if label corresponds to .mat
            _y_data = cur_data_dict['y'][idx]  # DEBUG
            _y_mat = _labels[row.filename]  # DEBUG
            if _y_data != _y_mat:  # DEBUG
                _diff_labels += 1  # DEBUG
                raise ValueError('Wrong label!')  # DEBUG
            # Ready mask and save images
            cur_mask = ready_mask(cur_mask, to_size=resize_shape,
                                  from_size=orig_shape)
            mask_img = Image.fromarray(cur_mask)
            mask_img.save(mask_dir / cur_name)
            # Ready iris and save images
            iris_img = ready_iris(iris, to_size=resize_shape,
                                  from_size=orig_shape)
            iris_img.save(iris_dir / cur_name)
            # Generate and save visualization
            if gen_new_visualization:
                vis = generate_visualization(np.array(iris_img).flatten(),
                                             cur_mask.flatten()/255,
                                             resize_shape)
                vis_img = Image.fromarray(vis)
                vis_img.save(vis_dir / cur_name)
            # Generate and save old mask visualization
            if gen_old_visualization:
                old_mask = ready_mask(old_mask, to_size=resize_shape,
                                      from_size=orig_shape)
                old_vis = generate_visualization(np.array(iris_img).flatten(),
                                                 old_mask.flatten()/255,
                                                 resize_shape)
                old_vis_img = Image.fromarray(old_vis)
                old_vis_img.save(old_vis_dir / cur_name)

    if old_dir is not None:
        chdir(old_dir)
