# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

from __future__ import division, unicode_literals

"""
OpenBabel interface module, which opens up access to the hundreds of file
formats supported by OpenBabel. Requires openbabel with python bindings to be
installed. Please consult the
`openbabel documentation <http://openbabel.org/wiki/Main_Page>`_.
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__date__ = "Apr 28, 2012"

from pymatgen.core.structure import Molecule
from monty.dev import requires

try:
    import openbabel as ob
    import pybel as pb
except:
    pb = None
    ob = None


class BabelMolAdaptor(object):
    """
    Adaptor serves as a bridge between OpenBabel's Molecule and pymatgen's
    Molecule.
    """

    @requires(pb and ob,
              "BabelMolAdaptor requires openbabel to be installed with "
              "Python bindings. Please get it at http://openbabel.org.")
    def __init__(self, mol):
        """
        Initializes with pymatgen Molecule or OpenBabel"s OBMol.

        Args:
            mol: pymatgen's Molecule or OpenBabel OBMol
        """
        if isinstance(mol, Molecule):
            if not mol.is_ordered:
                raise ValueError("OpenBabel Molecule only supports ordered "
                                 "molecules.")

            # For some reason, manually adding atoms does not seem to create
            # the correct OBMol representation to do things like force field
            # optimization. So we go through the indirect route of creating
            # an XYZ file and reading in that file.
            obmol = ob.OBMol()

            obmol = ob.OBMol()
            obmol.BeginModify()
            for site in mol:
                coords = [c for c in site.coords]
                atomno = site.specie.Z
                obatom = ob.OBAtom()
                obatom.thisown = 0
                obatom.SetAtomicNum(atomno)
                obatom.SetVector(*coords)
                obmol.AddAtom(obatom)
                del obatom
            obmol.ConnectTheDots()
            obmol.PerceiveBondOrders()
            obmol.SetTotalSpinMultiplicity(mol.spin_multiplicity)
            obmol.SetTotalCharge(mol.charge)
            obmol.Center()
            obmol.Kekulize()
            obmol.EndModify()
            self._obmol = obmol
        elif isinstance(mol, ob.OBMol):

            self._obmol = mol

    @property
    def pymatgen_mol(self):
        """
        Returns pymatgen Molecule object.
        """
        sp = []
        coords = []
        for atom in ob.OBMolAtomIter(self._obmol):
            sp.append(atom.GetAtomicNum())
            coords.append([atom.GetX(), atom.GetY(), atom.GetZ()])
        return Molecule(sp, coords)

    @property
    def openbabel_mol(self):
        """
        Returns OpenBabel's OBMol.
        """
        return self._obmol

    def localopt(self, forcefield='mmff94', steps=500):
        """
        A wrapper to pybel's localopt method to optimize a Molecule.

        Args:
            forcefield: Default is mmff94. Options are 'gaff', 'ghemical',
                'mmff94', 'mmff94s', and 'uff'.
            steps: Default is 500.
        """
        pbmol = pb.Molecule(self._obmol)
        pbmol.localopt(forcefield=forcefield, steps=steps)
        self._obmol = pbmol.OBMol

    def confm_search(self, forcefield="mmff94", freeze_atoms=None,
                     rmsd_cutoff=0.5, energy_cutoff=50.0,
                     conf_cutoff=100000, verbose=False, make_3d=False,
                     add_hydrogens=False):
        """
        Perform conformer search.
        Args:
            forcefield: Default is mmff94. Options are 'gaff', 'ghemical',
                'mmff94', 'mmff94s', and 'uff'.
            freeze_atoms: List of indices of atoms to be fixed during search.
            rmsd_cutoff:
            energy_cutoff:
            conf_cutoff:
            verbose: For conformer generation output
            make_3d: Should conformer search be performed in 2D or 3D
            add_hydrogens: Should implicit Hydrogens be added?
        Returns: BabelMolAdapter

        """

        obmol = self.openbabel_mol

        if make_3d:
            builder = ob.OBBuilder()
            builder.Build(obmol)

        if add_hydrogens:
            obmol.AddHydrogens()

        ff = ob.OBForceField_FindType(forcefield)
        if ff == 0:
            print("Could not find forcefield {} in openbabel, the forcefield "
                  "will be reset as default 'mmff94'".format(forcefield))
            ff = ob.OBForceField_FindType("mmff94")

        if freeze_atoms:
            print('{} atoms will be freezed'.format(len(freeze_atoms)))
            constraints = ob.OBFFConstraints()
            for atom in ob.OBMolAtomIter(self.openbabel_mol):
                atom_id = atom.GetIndex() + 1
                if id in freeze_atoms:
                    constraints.AddAtomConstraint(atom_id)
            ff.SetConstraints(constraints)

        # To improve 3D coordinates
        ff.WeightedRotorSearch(500, 25)

        # Run Confab conformer generation
        ff.DiverseConfGen(rmsd_cutoff, conf_cutoff, energy_cutoff,
                          verbose)

        ff.GetConformers(obmol)

        if verbose:
            print("Generated {} conformers total".format(obmol.NumConformers()))

        self._obmol = obmol

    @property
    def pybel_mol(self):
        """
        Returns Pybel's Molecule object.
        """
        return pb.Molecule(self._obmol)

    def write_file(self, filename, file_format="xyz"):
        """
        Uses OpenBabel to output all supported formats.

        Args:
            filename: Filename of file to output
            file_format: String specifying any OpenBabel supported formats.
        """
        mol = pb.Molecule(self._obmol)
        return mol.write(file_format, filename, overwrite=True)

    @staticmethod
    def from_file(filename, file_format="xyz"):
        """
        Uses OpenBabel to read a molecule from a file in all supported formats.

        Args:
            filename: Filename of input file
            file_format: String specifying any OpenBabel supported formats.

        Returns:
            BabelMolAdaptor object
        """
        mols = list(pb.readfile(str(file_format), str(filename)))
        return BabelMolAdaptor(mols[0].OBMol)

    @staticmethod
    def from_string(string_data, file_format="xyz"):
        """
        Uses OpenBabel to read a molecule from a string in all supported
        formats.

        Args:
            string_data: String containing molecule data.
            file_format: String specifying any OpenBabel supported formats.

        Returns:
            BabelMolAdaptor object
        """
        mols = pb.readstring(str(file_format), str(string_data))
        return BabelMolAdaptor(mols.OBMol)
