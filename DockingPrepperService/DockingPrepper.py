import subprocess
import os
import logging

class DockingPrepperException(Exception):
    def __init__(self, error):
        self.error = error

class DockingPrepper():
    def __init__(self, config):
        self.logger = logging.getLogger("DockingPrepperService.DockingPrepper")
        self.config = config

    def removeRotamers(self, file, outfile):
        deleternadna = True

        rnaResidues = ['A', 'G', 'C', 'U', 'I']
        dnaResidues = ['DA', 'DG', 'DC', 'DT', 'DI']
        toDelete = rnaResidues + dnaResidues

        with open(file, "r") as fil:
            with open(outfile, "w") as out:
                for line in fil:
                    if line.startswith("ATOM") or line.startswith("HETATM"):
                        if deleternadna and (line[17:20].strip() in toDelete):
                            continue
                        if line[16:17] != ' ' and line[16:17] != 'A':
                            continue
                    out.write(line)

    def preparePDBQTLigand(self, fullPath: str) -> str:
        log = ""
        self.logger.info(f"Creating PDBQT for ligand {fullPath}")
        path, ext = os.path.splitext(fullPath)
        outputPath = path + ".pdbqt"
        pythonsh = subprocess.run([self.config["babelpath"],
                                   "-imol2",
                                   fullPath,
                                   "-p",
                                   "-O",
                                   outputPath],
                                   text=True, capture_output=True)
        if pythonsh.returncode != 0:
            self.logger.error(pythonsh.stderr)
            raise DockingPrepperException(pythonsh.stderr)
        log += pythonsh.stdout
        log += pythonsh.stderr
        self.logger.info("OpenBabel output:\n" + log)
        return outputPath

    def preparePDBQTReceptor(self, fullPath: str) -> str:
        """ Four steps:
                1. Remove rotamers, DNA and RNA
                2. Apply PDBFixer
                3. Protonation using PDB2PQR
                4. Create PDBQT using MGLTools
        """
        log = ""
        path, ext = os.path.splitext(fullPath)
        # ---------------------------------------------
        self.logger.info(f"Remove rotamers, DNA and RNA from {fullPath}")
        noRotamersPath = path + "_no_rotamers.pdb"
        self.removeRotamers(fullPath, noRotamersPath)
        # ---------------------------------------------
        self.logger.info(f"Applying PDBFixer for receptor {noRotamersPath}")
        fixedOutputPath = path + "_fixed.pdb"
        fixer = subprocess.run([self.config["condapath"],
                                self.config["pdbfixerpath"],
                                   noRotamersPath,
                                   fixedOutputPath],
                                   # "--keep-heterogens=none",
                                   # "--add-atoms=heavy",
                                   # "--replace-nonstandard",
                                   # "--add-residues"],
                                   text=True, capture_output=True)
        if fixer.returncode != 0:
            self.logger.error(fixer.stderr)
            raise DockingPrepperException(fixer.stderr)
        log += fixer.stdout
        log += fixer.stderr
        self.logger.info("PDBFixer output:\n" + fixer.stdout + fixer.stderr)
        self.logger.info("Removing: " + noRotamersPath)
        os.remove(noRotamersPath)
        # ---------------------------------------------
        self.logger.info(f"Protonation using PDB2PQR for receptor {fixedOutputPath}")
        protonatedOutputPath = path + "_protonated.pqr"
        pqr = subprocess.run([self.config["pdb2pqrpath"],
                              "--ff", "AMBER",
                              "--with-ph", "7.0",
                              "--titration-state-method", "propka",
                              "--quiet",
                              fixedOutputPath,
                              protonatedOutputPath],
                              text=True, capture_output=True)
        if pqr.returncode != 0:
            self.logger.error(pqr.stderr)
            raise DockingPrepperException(pqr.stderr)
        log += pqr.stdout
        log += pqr.stderr
        self.logger.info("PDB2PQR output:\n" + pqr.stdout + pqr.stderr)
        self.logger.info("Removing: " + fixedOutputPath)
        os.remove(fixedOutputPath)
        self.logger.info("Removing: " + path + "_protonated.log")
        os.remove(path + "_protonated.log")
        # ---------------------------------------------
        outputPath = path + "_protonated.pdbqt"
        self.logger.info(f"Creating PDBQT for fixed receptor {protonatedOutputPath} to {outputPath}")
        pythonsh = subprocess.run([self.config["pythonshpath"],
                                   self.config["preparereceptorpath"],
                                   "-r",
                                   protonatedOutputPath,
                                   "-A", "bonds"
                                   "-U", "nphs",
                                   "-o", outputPath],
                                   text=True, capture_output=True)
        if pythonsh.returncode != 0:
            self.logger.error(pythonsh.stderr)
            raise DockingPrepperException(pythonsh.stderr)
        log += pythonsh.stdout
        log += pythonsh.stderr
        self.logger.info("MGLTools output:\n" + pythonsh.stdout + pythonsh.stderr)
        self.logger.info("Removing: " + protonatedOutputPath)
        os.remove(protonatedOutputPath)
        return outputPath

    def prepareConfig(self, fullPath: str):
        self.logger.info(f"Creating config file for {fullPath}")
        xmin = 1000000000000
        ymin = 1000000000000
        zmin = 1000000000000
        xmax = -1000000000000
        ymax = -1000000000000
        zmax = -1000000000000

        with open(fullPath, "r") as file:
            for line in file.readlines():
                if line[0:4] == "ATOM":
                    x = float(line[31:39])
                    y = float(line[39:46])
                    z = float(line[46:55])
                    xmin, xmax = min(xmin, x), max(xmax, x)
                    ymin, ymax = min(ymin, y), max(ymax, y)
                    zmin, zmax = min(zmin, z), max(zmax, z)

        sizex = xmax - xmin
        sizey = ymax - ymin
        sizez = zmax - zmin

        offsetx = xmin + sizex / 2.0
        offsety = ymin + sizey / 2.0
        offsetz = zmin + sizez / 2.0

        with open(fullPath + "_conf", "w") as file:
            file.write("center_x = %f\n" % offsetx)
            file.write("center_y = %f\n" % offsety)
            file.write("center_z = %f\n\n" % offsetz)
            file.write("size_x = %f\n" % (sizex + 30))
            file.write("size_y = %f\n" % (sizey + 30))
            file.write("size_z = %f\n" % (sizez + 30))

        return fullPath + "_conf"