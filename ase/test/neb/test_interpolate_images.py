from ase import Atoms
from ase.neb import NEB
import numpy as np
import pytest


@pytest.fixture
def initial():
    return Atoms('H', positions=[(1, 0.1, 0.1)], cell=[
        [1, 0, 0], [0, 1, 0], [0, 0, 1]], pbc=True)


@pytest.fixture
def final():
    return Atoms('H', positions=[(2, 0.2, 0.1)], cell=[
        [2, 0, 0], [0, 2, 0], [0, 0, 2]], pbc=True)


@pytest.fixture
def average_pos(initial, final):
    return np.average([initial.positions, final.positions], axis=0)


@pytest.fixture
def images(initial, final):
    images = [initial.copy()]
    images += [initial.copy()]
    images += [final.copy()]
    return images


@pytest.fixture
def neb(images):
    return NEB(images)


def test_interpolate_images_default(neb, images, initial, average_pos):
    neb.interpolate()
    assert images[1].positions == pytest.approx(average_pos)
    assert np.allclose(images[1].cell, initial.cell)


def test_interpolate_images_scaled_coord(neb, images, initial):
    neb.interpolate(use_scaled_coord=True)
    assert np.allclose(images[1].positions, [1.0, 0.1, 0.075])
    assert np.allclose(images[1].cell, initial.cell)


def test_interpolate_images_cell(neb, images, initial, average_pos):
    neb.interpolate(interpolate_cell=True)
    assert images[1].positions == pytest.approx(average_pos)
    assert np.allclose(images[1].cell, initial.cell * 1.5)


def test_interpolate_images_cell_default_interpolate_cell_scaled_coord(
        neb,
        images,
        initial):
    neb.interpolate(interpolate_cell=True, use_scaled_coord=True)
    assert np.allclose(images[1].positions, [1.5, 0.15, 0.1125])
    assert np.allclose(images[1].cell, initial.cell * 1.5)
