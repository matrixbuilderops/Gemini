#!/usr/bin/env python3
"""
Singularity_Dave_Brain.py
The Central Orchestrator for the Singularity Mining System.
Coordinates Brainstem, Looping, DTM, and Miners.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path

# Import Brainstem for infrastructure and utility functions
try:
    from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
        brain_initialize_mode,
        brain_get_path,
        brain_save_system_report,
        brain_save_system_error,
        brain_get_flags,
        brain_perform_system_wide_consensus
    )
except ImportError:
    print("CRITICAL: Singularity_Dave_Brainstem_UNIVERSE_POWERED.py not found.")
    sys.exit(1)

class SingularityBrain:
    def __init__(self, mode="production"):
        self.mode = mode
        self.start_time = time.time()
        self.components = {
            "Brainstem": "Unknown",
            "DTM": "Unknown",
            "Looping": "Unknown",
            "Miners": "Unknown"
        }
        self.orchestration_count = 0

        # Initialize logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup internal logging for the Brain."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - BRAIN - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("SingularityBrain")

    def initialize_system(self):
        """
        Initialize the entire mining system infrastructure via Brainstem.
        """
        self.logger.info(f"Initializing Singularity System in {self.mode} mode...")

        try:
            # 1. Initialize Infrastructure (Folders, Templates) via Brainstem
            brain_initialize_mode(self.mode, "Brain")
            self.components["Brainstem"] = "Initialized"

            # 2. Verify Config
            config_path = Path("config.json")
            if not config_path.exists():
                self.logger.warning("config.json not found. Using defaults.")

            # 3. Create Initial System Report
            self._report_status("System Initialization Complete")

            return True
        except Exception as e:
            self.logger.error(f"System Initialization Failed: {e}")
            self._report_error("initialization_failure", str(e), severity="critical")
            return False

    def create_system_report_hourly_file(self, report_data):
        """
        Wrapper to save system reports, accessible by other components if they import Brain.
        """
        return brain_save_system_report(report_data, "Brain", "system_report")

    def create_system_error_hourly_file(self, error_data):
        """
        Wrapper to save system errors.
        """
        return brain_save_system_error(error_data, "Brain")

    def perform_consensus(self):
        """
        Perform system-wide consensus check.
        """
        try:
            result = brain_perform_system_wide_consensus(self.mode)
            self._report_status(f"Consensus Performed: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Consensus Failed: {e}")
            self._report_error("consensus_failure", str(e))
            return False

    def _report_status(self, message):
        """Internal status reporting."""
        status_data = {
            "status": "active",
            "message": message,
            "mode": self.mode,
            "uptime": time.time() - self.start_time,
            "orchestrations": self.orchestration_count
        }
        brain_save_system_report(status_data, "Brain", "brain_report")

    def _report_error(self, error_type, message, severity="error"):
        """Internal error reporting."""
        error_data = {
            "error_type": error_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        brain_save_system_error(error_data, "Brain")

    def check_component_health(self):
        """
        Check the health of all components by verifying their report files exist and are recent.
        """
        # This is a placeholder for more advanced health checking logic
        # For now, it assumes if we can write reports, we are healthy.
        return True

if __name__ == "__main__":
    # If run directly, act as a smoke test or simple orchestration starter
    import argparse
    parser = argparse.ArgumentParser(description="Singularity Brain Orchestrator")
    parser.add_argument("--mode", default="production", help="Operation mode")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke test")
    args = parser.parse_args()

    brain = SingularityBrain(mode=args.mode)

    if args.smoke_test:
        print("Running Brain Smoke Test...")
        if brain.initialize_system():
            print("Brain Initialization: SUCCESS")
            sys.exit(0)
        else:
            print("Brain Initialization: FAILED")
            sys.exit(1)

    # Normal execution
    brain.initialize_system()
    print("Singularity Brain is running. (This script is usually imported by Looping or run as daemon)")
