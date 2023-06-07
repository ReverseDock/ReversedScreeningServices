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
        log = ""
        self.logger.info(f"Creating PDBQT for receptor {fullPath}")
        path, ext = os.path.splitext(fullPath)
        outputPath = path + ".pdbqt"
        pythonsh = subprocess.run([self.config["pythonshpath"],
                                   self.config["preparereceptorpath"],
                                   "-r",
                                   fullPath,
                                   "-A", "bonds_hydrogens",
                                   "-U", "nphs",
                                   "-o", outputPath],
                                   text=True, capture_output=True)
        if pythonsh.returncode != 0:
            self.logger.error(pythonsh.stderr)
            raise DockingPrepperException(pythonsh.stderr)
        log += pythonsh.stdout
        log += pythonsh.stderr
        self.logger.info("MGLTools output:\n" + log)
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