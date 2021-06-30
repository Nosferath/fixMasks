import unittest

import numpy as np

from fixMasks.iris import IrisImage


class TestIrisImage(unittest.TestCase):
    def setUp(self) -> None:
        iris_a = np.random.randint(0, 256, (3, 3, 3))
        mask_a = np.zeros((3, 3))
        mask_b = np.ones((3, 3))
        shape = (3, 3, 1)
        self.image_a = IrisImage(iris_a.flatten(), mask_a.flatten(), shape)
        self.image_b = IrisImage(iris_a.flatten(), mask_b.flatten(), shape)

    def test_draw(self):
        expected = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
        self.image_a.draw_on_mask((1, 1), 1)
        self.assertTrue(np.all(expected.flatten() == self.image_a.mask))

    def test_erase(self):
        expected = np.array([[1, 0, 1], [0, 0, 0], [1, 0, 1]])
        self.image_b.erase_on_mask((1, 1), radius=1)
        self.assertTrue(np.all(expected.flatten() == self.image_b.mask))

    def test_undo(self):
        expected = np.zeros((3, 3))
        self.image_a.draw_on_mask((1, 1), 1)
        self.image_a.undo()
        self.assertTrue(np.all(expected.flatten() == self.image_a.mask))

    def test_redo(self):
        expected = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
        self.image_a.draw_on_mask((1, 1), 1)
        self.image_a.undo()
        self.image_a.redo()
        self.assertTrue(np.all(expected.flatten() == self.image_a.mask))
