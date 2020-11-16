from itertools import chain
import warnings

import ele
import mbuild as mb
import numpy as np
from numpy.linalg import norm


__all__ = ['write_poscar', 'read_poscar']

def write_poscar(
        compound, filename, lattice_constant=1.0, coord='cartesian'
        ):
    """
    Outputs VASP POSCAR files.  See //https://www.vasp.at for
    more information.

    Parameters
    ----------
    compound : mbuild.Compound
        The Compound to write to the POSCAR file
    filename : str
        Path of the output file
    lattice_constant : float
        Scaling constant for POSCAR file, used to scale all lattice vectors
        and atomic coordinates
        (default 1.0)
    coord_style : str
        Coordinate style of atom positions 'cartesian' or 'direct'
        (default 'cartesian')
    """
    try:
        atoms = [p.element.symbol for p in compound.particles()]
    except AttributeError:
        for p in compound.particles():
            p.element = ele.element_from_symbol(p.name)
        atoms = [p.element.symbol for p in compound.particles()]

    # This automatically sorts element names alphabetically
    unique_atoms = np.unique(atoms)

    count_list = [str(atoms.count(i)) for i in unique_atoms]

    # This sorts the coordinates so they are in the same
    # order as the elements
    sorted_xyz = compound.xyz[np.argsort(atoms)]

    try:
        lattice = _box_to_lattice(compound.box)
    except AttributeError:
        lattice = _box_to_lattice(compound.boundingbox)
        if coord_style == "direct":
            warnings.warn(
                    "'direct' coord_style specified, but compound has no box "
                    "-- using 'cartesian' instead"
                    )
            coord_style = 'cartesian'

    if coord_style == 'cartesian':
        sorted_xyz /= lattice_constant
    elif coord_style == 'direct':
        sorted_xyz = sorted_xyz.dot(lattice) / lattice_constant
    else:
        raise ValueError("coord_style must be either 'cartesian' or 'direct'")

    with open(filename, 'w') as f:
        f.write(filename+' - created by mBuild\n')
        f.write(f'\t{lattice_constant:.15f}\n')

        f.write('\t{0:.15f} {1:.15f} {2:.15f}\n'.format(*lattice[0]))
        f.write('\t{0:.15f} {1:.15f} {2:.15f}\n'.format(*lattice[1]))
        f.write('\t{0:.15f} {1:.15f} {2:.15f}\n'.format(*lattice[2]))
        f.write("{}\n".format('\t'.join(unique_atoms)))
        f.write("{}\n".format('\t'.join(count_list)))
        f.write(f"{coord_style}\n")
        for xyz in sorted_xyz:
            f.write(" ".join([f"{i:.15f}" for i in row])+"\n")


def read_poscar(filename, conversion=0.1):
    """
    Reads in a VASP POSCAR or CONTCAR file and returns an mbuild Compound.

    Parameters
    ----------
    filename : str
        path to the POSCAR file
    conversion : float
        conversion factor multiplied to coordinates when converting between
        VASP units (angstroms) and mbuild units (nm) (default = 0.1)

    Returns
    -------
    mbuild.Compound
    """

    comp = mb.Compound()

    with open(filename, "r") as f:
        data = f.readlines()

    title = data.pop(0)
    scale = float(data.pop(0).strip())

    a = np.fromiter(data.pop(0).split(), dtype="float64")
    b = np.fromiter(data.pop(0).split(), dtype="float64")
    c = np.fromiter(data.pop(0).split(), dtype="float64")

    lattice_vectors = np.stack((a,b,c))

    # POSCAR files do not require atom types to be specified
    # this block handles unspecified types
    line = data.pop(0).split()
    try:
        n_types = np.fromiter(line, dtype="int")
        types = ["_"+chr(i+64) for i in range(1,len(n_types)+1)]
        # if no types exist, assign placeholder types "_A", "_B", "_C", etc
    except ValueError:
        types = line
        n_types = np.fromiter(data.pop(0).split(), dtype="int")

    total_atoms = np.sum(n_types)
    all_types = list(chain.from_iterable(
        [[itype] * n for itype, n in zip(types,n_types)]
        ))

    # handle optional argument "Selective dynamics"
    # and required arguments "Cartesian" or "Direct"
    switch = data.pop(0)[0].upper()
    selective_dynamics = False # don't know if this is necessary
    if switch == "S":
        selective_dynamics = True
        switch = data.pop(0)[0].upper()

    if switch == "C":
        cartesian = True
    else:
        cartesian = False

    # Slice is necessary to handle files using selective dynamics
    coords = np.stack([np.fromiter(
        line.split()[:3], dtype="float64"
        ) for line in data[:total_atoms]])

    if cartesian:
        coords = coords * scale
    else:
        coords = coords.dot(lattice_vectors) * scale

    comp.box = _lattice_to_box(lattice_vectors)

    for i,xyz in enumerate(coords):
        comp.add(mb.Particle(
            name=all_types[i],
            element=ele.element_from_symbol(all_types[i]),
            pos=xyz*conversion
            ))

    return comp


def _box_to_lattice(box):
    """
    http://gisaxs.com/index.php/Unit_cell
    """
    lengths = box.maxs - box.mins
    alpha, beta, gamma = [np.deg2rad(a) for a in box.angles]

    a = np.array([lengths[0], 0, 0])
    b = np.array([
        lengths[1] * np.cos(gamma),
        lengths[1] * np.sin(gamma),
        0
    ])

    fraction = (np.cos(alpha) - np.cos(beta)*np.cos(gamma)) / np.sin(gamma)
    c = np.array([
        lengths[2] * np.cos(beta),
        lengths[2] * fraction,
        lengths[2] * np.sqrt(1 - np.cos(beta)**2 - fraction**2)
    ])
    return np.stack((a,b,c))


def _lattice_to_box(lattice_vectors):
    a,b,c = lattice
    alpha = np.rad2deg(np.arccos(b.dot(c)/(norm(b) * norm(c))))
    beta = np.rad2deg(np.arccos(a.dot(c)/(norm(a) * norm(c))))
    gamma = np.rad2deg(np.arccos(a.dot(b)/(norm(a) * norm(b))))

    box = mb.Box(
            lengths=norm(lattice_vectors, axis=1),
            angles=[alpha, beta, gamma]
            )
    return box
