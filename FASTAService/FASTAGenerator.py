import subprocess
import logging

class FASTAGenerator():
    def __init__(self, config):
        self.logger = logging.getLogger("FASTAService.FASTAGenerator")
        self.config = config

    def getFASTA(self, path: str) -> str:
        self.logger.info("Generating FASTA using OpenBabel")
        result = subprocess.run([self.config["babelpath"], path, "-ofasta"], capture_output=True, text=True).stdout
        if result == "":
            return ""
        self.logger.info(f"OpenBabel output:\n{result}")
        fasta = "".join(result.split('\n')[1:])
        self.logger.info(f"Extracted FASTA: {fasta}")
        return fasta
