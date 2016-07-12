import numpy as np

from ase.atoms import Atoms
from ase.units import Hartree
from ase.parallel import paropen
from ase.data import atomic_numbers
from ase.calculators.singlepoint import SinglePointCalculator


def write_xsf(fileobj, images, data=None):
    if isinstance(fileobj, str):
        fileobj = paropen(fileobj, 'w')

    if not isinstance(images, (list, tuple)):
        images = [images]

    is_anim = len(images) > 1

    if is_anim:
        fileobj.write('ANIMSTEPS %d\n' % len(images))

    numbers = images[0].get_atomic_numbers()

    pbc = images[0].get_pbc()
    npbc = sum(pbc)
    if pbc[2]:
        fileobj.write('CRYSTAL\n')
        assert npbc == 3
    elif pbc[1]:
        fileobj.write('SLAB\n')
        assert npbc == 2
    elif pbc[0]:
        fileobj.write('POLYMER\n')
        assert npbc == 1
    else:
        # (Header written as part of image loop)
        assert npbc == 0

    cell_variable = False
    for image in images[1:]:
        if np.abs(images[0].cell - image.cell).max() > 1e-14:
            cell_variable = True
            break

    for n, atoms in enumerate(images):
        anim_token = ' %d' % (n + 1) if is_anim else ''
        if pbc.any():
            write_cell = (n == 0 or cell_variable)
            if write_cell:
                if cell_variable:
                    fileobj.write('PRIMVEC%s\n' % anim_token)
                else:
                    fileobj.write('PRIMVEC\n')
                cell = atoms.get_cell()
                for i in range(3):
                    fileobj.write(' %.14f %.14f %.14f\n' % tuple(cell[i]))

            fileobj.write('PRIMCOORD%s\n' % anim_token)
        else:
            fileobj.write('ATOMS%s\n' % anim_token)

        # Get the forces if it's not too expensive:
        calc = atoms.get_calculator()
        if (calc is not None and
            (hasattr(calc, 'calculation_required') and
             not calc.calculation_required(atoms, ['forces']))):
            forces = atoms.get_forces() / Hartree
        else:
            forces = None

        pos = atoms.get_positions()

        if pbc.any():
            fileobj.write(' %d 1\n' % len(pos))
        for a in range(len(pos)):
            fileobj.write(' %2d' % numbers[a])
            fileobj.write(' %20.14f %20.14f %20.14f' % tuple(pos[a]))
            if forces is None:
                fileobj.write('\n')
            else:
                fileobj.write(' %20.14f %20.14f %20.14f\n' % tuple(forces[a]))

    if data is None:
        return

    fileobj.write('BEGIN_BLOCK_DATAGRID_3D\n')
    fileobj.write(' data\n')
    fileobj.write(' BEGIN_DATAGRID_3Dgrid#1\n')

    data = np.asarray(data)
    if data.dtype == complex:
        data = np.abs(data)

    shape = data.shape
    fileobj.write('  %d %d %d\n' % shape)

    cell = atoms.get_cell()
    origin = np.zeros(3)
    for i in range(3):
        if not pbc[i]:
            origin += cell[i] / shape[i]
    fileobj.write('  %f %f %f\n' % tuple(origin))

    for i in range(3):
        fileobj.write('  %f %f %f\n' %
                      tuple(cell[i] * (shape[i] + 1) / shape[i]))

    for x in range(shape[2]):
        for y in range(shape[1]):
            fileobj.write('   ')
            fileobj.write(' '.join(['%f' % d for d in data[x, y]]))
            fileobj.write('\n')
        fileobj.write('\n')

    fileobj.write(' END_DATAGRID_3D\n')
    fileobj.write('END_BLOCK_DATAGRID_3D\n')


def read_xsf(fileobj, index=-1, read_data=False):
    if isinstance(fileobj, str):
        fileobj = open(fileobj)

    def _line_generator_func():
        for line in fileobj:
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Discard comments and empty lines
            yield line

    _line_generator = _line_generator_func()

    def readline():
        return next(_line_generator)

    line = readline()

    if line.startswith('ANIMSTEPS'):
        nimages = int(line.split()[1])
        line = readline()
    else:
        nimages = 1

    if line == 'CRYSTAL':
        pbc = (True, True, True)
    elif line == 'SLAB':
        pbc = (True, True, False)
    elif line == 'POLYMER':
        pbc = (True, False, False)
    else:
        assert line.startswith('ATOMS'), line  # can also be ATOMS 1
        pbc = (False, False, False)

    images = []
    cell = None
    for n in range(nimages):
        if any(pbc):
            line = readline()
            if line.startswith('PRIMCOORD'):
                assert cell is not None  # cell read from previous image
            else:
                assert line.startswith('PRIMVEC')
                cell = []
                for i in range(3):
                    cell.append([float(x) for x in readline().split()])

                line = readline()
                if line.startswith('CONVVEC'):  # ignored;
                    for i in range(3):
                        readline()
                    line = readline()

            assert line.startswith('PRIMCOORD')
            natoms = int(readline().split()[0])
            lines = [readline() for _ in range(natoms)]
        else:
            assert line.startswith('ATOMS'), line
            line = readline()
            lines = []
            while line[:1].isdigit():
                lines.append(line)
                try:
                    line = readline()
                except StopIteration:
                    break
            if line.startswith('BEGIN'):
                # We read "too far" and accidentally got the header
                # of the data section.  This happens only when parsing
                # ATOMS blocks, because one cannot infer their length.
                # We will remember the line until later then.
                data_header_line = line

        numbers = []
        positions = []
        for positionline in lines:
            tokens = positionline.split()
            symbol = tokens[0]
            if symbol.isdigit():
                numbers.append(int(symbol))
            else:
                numbers.append(atomic_numbers[symbol])
            positions.append([float(x) for x in tokens[1:]])

        positions = np.array(positions)
        if len(positions[0]) == 3:
            forces = None
        else:
            forces = positions[:, 3:] * Hartree
            positions = positions[:, :3]

        image = Atoms(numbers, positions, cell=cell, pbc=pbc)

        if forces is not None:
            image.set_calculator(SinglePointCalculator(image, forces=forces))
        images.append(image)

    if read_data:
        if any(pbc):
            line = readline()
        else:
            line = data_header_line
        assert line.startswith('BEGIN_BLOCK_DATAGRID_3D')
        readline()  # name
        line = readline()
        assert line.startswith('BEGIN_DATAGRID_3D')

        shape = [int(x) for x in readline().split()]
        readline()  # start

        for i in range(3):
            readline()

        n_data = shape[0] * shape[1] * shape[2]
        data = np.array([float(readline())
                         for s in range(n_data)]).reshape(shape[::-1])
        data = np.swapaxes(data, 0, 2)

        return data, images[index]

    return images[index]
