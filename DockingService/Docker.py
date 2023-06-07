import subprocess
from pathlib import Path
import os
import re
import logging

class DockerException(Exception):
    def __init__(self, error):
        self.error = error

class Docker():
    def __init__(self, config):
        self.regex = re.compile(r'\n   1[ ]*([-.0-9]+)')
        self.logger = logging.getLogger("DockingService.Docker")
        self.config = config

    def runDocking(self, fullLigandPath, fullReceptorPath, fullConfigPath, exhaustiveness):
        """
        """
        log = ""
        affinity: float = 1000
        receptorFilenameWithExt = os.path.basename(fullReceptorPath)
        receptorFilename, ext = os.path.splitext(receptorFilenameWithExt)
        ligandFilename, lext = os.path.splitext(fullLigandPath)
        outputdir = os.path.join(os.path.dirname(fullLigandPath), ligandFilename + "_docked_to_" + receptorFilename + ".pdbqt")
        self.logger.info(f"Starting AutoDock Vina process")
        docking = subprocess.run([self.config["vinapath"],
                                  "--config", fullConfigPath,
                                  "--exhaustiveness",
                                  str(exhaustiveness),
                                  "--receptor", fullReceptorPath,
                                  "--ligand", fullLigandPath,
                                  "--cpu",
                                  str(min(exhaustiveness, 4)), # adjust maximum amount of CPUs according to number of workers and CPUs
                                  "--energy_range",
                                  "5",
                                  "--out",
                                  outputdir], 
                                  text=True, capture_output=True)
        log += docking.stdout
        log += docking.stderr
        self.logger.info(f"AutoDock Vina finished.")
        try:
            if docking.returncode != 0:
                raise Exception()
            affinity = float(self.regex.findall(log)[0])
        except Exception:
            self.logger.error(docking.stderr)
            raise DockerException(docking.stderr)
       
        self.logger.info(f"Extracted affinity from output: {affinity}")

        return affinity, outputdir