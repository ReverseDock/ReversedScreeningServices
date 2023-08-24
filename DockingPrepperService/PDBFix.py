import sys
import json
from pdbfixer import PDBFixer
from simtk.openmm.app import PDBFile

file = sys.argv[1]
outfile = sys.argv[2]

fixer = PDBFixer(filename=file)
# delete all but the first chain
chains = list(fixer.topology.chains())
if len(chains) > 1:
    fixer.removeChains([i for i in range(1,len(chains))])
# Find missing residues
fixer.findMissingResidues()
# begin: Only insert missing residues in the middle
keys = list(fixer.missingResidues.keys())
for key in keys:
    chain = chains[key[0]]
    if key[1] == 0 or key[1] == len(list(chain.residues())):
        del fixer.missingResidues[key]
# end
fixer.findNonstandardResidues()
fixer.replaceNonstandardResidues()
fixer.removeHeterogens(False)
fixer.findMissingAtoms()
fixer.addMissingAtoms()
PDBFile.writeFile(fixer.topology, fixer.positions, open(outfile, 'w'), keepIds=True)