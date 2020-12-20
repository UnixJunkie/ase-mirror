import sys
import os
import numpy as np
from ase.calculators.socketio import SocketIOCalculator, PySocketIOClient
from ase.calculators.emt import EMT


def calculator_factory():
    return EMT()


def test_socketio_python():
    from ase.build import bulk
    from ase.constraints import ExpCellFilter
    from ase.optimize import BFGS

    atoms = bulk('Au') * (2, 2, 2)
    atoms.rattle(stdev=0.05)
    fmax = 0.01
    atoms.cell += np.random.RandomState(42).rand(3, 3) * 0.05

    client = PySocketIOClient(calculator_factory)

    pid = os.getpid()
    with SocketIOCalculator(launch_client=client,
                            unixsocket='ase-python-{pid}') as atoms.calc:
        opt = BFGS(ExpCellFilter(atoms))
        opt.run(fmax=fmax)
    forces = atoms.get_forces()
    assert np.linalg.norm(forces, axis=0).max() < fmax
