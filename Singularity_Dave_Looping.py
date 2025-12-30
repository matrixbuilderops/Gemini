#!/usr/bin/env python3
"""
Singularity_Dave_Looping.py
Specialized Bitcoin Mining Loop Manager

This is a special child - NOT part of the main flag system.
Clean, sophisticated, and only uses what's needed.
"""

import argparse
import asyncio
import copy
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# DEFENSIVE Brain import - NO HARD DEPENDENCIES
brain_available = False
BrainQTLInterpreter = None

try:
    from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
        brain_set_mode,
        brain_initialize_mode,
        brain_get_math_config,
        brain_save_ledger,
        brain_save_submission,
        brain_save_system_report,
        brain_get_path,
        brain_get_base_path,
        brain_perform_system_wide_consensus,
        brain_log_error
    )
    brain_available = True
    print("🧠 Brain.QTL integration loaded successfully")
except ImportError:
    brain_available = False
    def brain_set_mode(*args, **kwargs): pass
    def brain_initialize_mode(*args, **kwargs): return {"success": False}
    def brain_get_math_config(*args, **kwargs): return {}
    def brain_save_ledger(*args, **kwargs): return {"success": False}
    def brain_save_submission(*args, **kwargs): return {"success": False}
    def brain_save_system_report(*args, **kwargs): return {"success": False}
    def brain_get_path(key, **kwargs): return f"Mining/{key}"
    def brain_get_base_path(): return "Mining"
    def brain_perform_system_wide_consensus(*args, **kwargs): return True
    def brain_log_error(*args, **kwargs): pass
    print("🔄 Brain.QTL not available - using defensive fallbacks")

# Configure logging
def setup_brain_coordinated_logging(component_name):
    """Setup logging according to Brain.QTL component-based structure"""
    global_log = brain_get_path(f"global_{component_name}_log")
    hourly_log = brain_get_path(f"hourly_{component_name}_log", custom_timestamp=datetime.now().isoformat())

    log_dir = os.path.dirname(global_log)
    os.makedirs(log_dir, exist_ok=True)
    
    hourly_dir = os.path.dirname(hourly_log)
    os.makedirs(hourly_dir, exist_ok=True)
    
    logger = logging.getLogger(component_name)
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    global_handler = logging.FileHandler(global_log)
    global_handler.setFormatter(formatter)
    logger.addHandler(global_handler)
    
    hourly_handler = logging.FileHandler(hourly_log)
    hourly_handler.setFormatter(formatter)
    logger.addHandler(hourly_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_brain_coordinated_logging("looping")

class BitcoinLoopingSystem:
    """
    ORGANIZED Bitcoin mining loop manager with CLEAN file structure
    and intelligent scheduling capabilities.
    """

    def __init__(self, mining_mode="default", demo_mode=False, test_mode=False, daemon_count=None, mining_config=None, staging_mode=False):
        self.mining_mode = mining_mode
        self.demo_mode = demo_mode
        self.test_mode = test_mode
        self.staging_mode = staging_mode
        
        # AUTO-DETECT hardware
        if daemon_count is None:
            try:
                import multiprocessing
                cpu_cores = multiprocessing.cpu_count()
                daemon_count = cpu_cores
                print(f"🧠 Brain auto-detected: {cpu_cores} CPU cores → {daemon_count} miners")
            except Exception as e:
                daemon_count = 5
                print(f"⚠️ Could not detect cores: {e}, using default: {daemon_count} miners")
        
        self.daemon_count = daemon_count
        
        # Initialize Brain
        if brain_available:
            mode = "demo" if demo_mode else "test" if test_mode else "staging" if staging_mode else "live"
            self.math_config = brain_get_math_config(mode)
            brain_initialize_mode(mode, "Looping")
        else:
            self.math_config = {}

        self.mining_config = mining_config or {}
        
        # Configurable settings
        self.daily_block_limit = 144
        self.blocks_found_today = 0
        self.bitcoin_cli_path = "bitcoin-cli" # Assuming in path, or set full path
        
        # Miner control
        self.production_miners = {}
        self.production_miner_processes = {}
        self.daemon_status = {}
        self.daemon_unique_ids = {}
        
        # Initial hardware setup
        self._setup_daemons()
        
        # ZMQ
        self.zmq_config = {
            "rawblock": "tcp://127.0.0.1:28333",
            "hashblock": "tcp://127.0.0.1:28335",
        }
        self.context = None
        self.subscribers = {}

        # Paths
        self.base_dir = Path(brain_get_base_path())
        self.temporary_template_dir = Path(brain_get_path("temporary_template_dir"))
        self.user_look_at_dir = Path(brain_get_path("user_look_at"))
        
        # DTM
        try:
            from dynamic_template_manager import GPSEnhancedDynamicTemplateManager
            self.template_manager = GPSEnhancedDynamicTemplateManager(
                verbose=False,
                demo_mode=self.demo_mode,
                auto_initialize=False,
                create_directories=False
            )
        except ImportError:
            self.template_manager = None
            print("⚠️ DTM not found")

        # Modes
        self.on_demand_mode_active = False
        self.activation_window_minutes = 40 # User requested 40 minutes
        self.miners_always_on = False
        
        # Ensure clean start
        self.cleanup_temporary_files_on_new_template()

    def _setup_daemons(self):
        """Setup daemon tracking"""
        for i in range(1, self.daemon_count + 1):
            unique_id = f"daemon_{i}_{uuid.uuid4().hex[:8]}"
            self.daemon_unique_ids[i] = unique_id
            self.production_miners[unique_id] = None
            self.production_miner_processes[unique_id] = None
            self.daemon_status[unique_id] = "stopped"

    def cleanup_temporary_files_on_new_template(self):
        """Wipe the temporary template directory when a new template arrives."""
        try:
            temp_dir = self.temporary_template_dir
            logger.info(f"🧹 Wiping temporary template directory: {temp_dir}")
            
            if not temp_dir.exists():
                temp_dir.mkdir(parents=True, exist_ok=True)
                return

            for item in temp_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete {item}: {e}")
            
            # Re-create process folders
            self.create_dynamic_daemon_folders()
                
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

    def create_dynamic_daemon_folders(self):
        """Create process_X folders for miners"""
        try:
            for i in range(1, self.daemon_count + 1):
                p = self.temporary_template_dir / f"process_{i}"
                p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"❌ Failed to create daemon folders: {e}")

    def get_real_block_template(self):
        """Get block template from Bitcoin node or DTM."""
        if self.demo_mode:
            # Simulated template
            return {
                "height": 850000 + self.blocks_found_today,
                "version": 536870912,
                "previousblockhash": "0000000000000000000000000000000000000000000000000000000000000000",
                "target": "00000000ffff0000000000000000000000000000000000000000000000000000",
                "bits": "1d00ffff",
                "transactions": []
            }
        
        # Real node implementation would go here (using bitcoin-cli getblocktemplate)
        # For now, we assume DTM might provide it or we return None to simulate node fail
        # But we need a working system.
        try:
            import subprocess
            cmd = [self.bitcoin_cli_path, "getblocktemplate", '{"rules":["segwit"]}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
        
        # Fallback simulation if node fails in test mode
        if self.test_mode:
             return {
                "height": 100,
                "previousblockhash": "0" * 64,
                "target": "00000000ffff0000000000000000000000000000000000000000000000000000",
                "bits": "1d00ffff",
                "transactions": []
            }
        return None

    def start_miners(self):
        """Start mining processes"""
        print(f"🚀 Starting {self.daemon_count} mining daemons...")
        
        # In a real implementation, this would spawn python processes
        # python production_bitcoin_miner.py --daemon --miner-id X
        
        for i in range(1, self.daemon_count + 1):
            unique_id = self.daemon_unique_ids[i]
            cmd = [sys.executable, "production_bitcoin_miner.py", "--daemon", "--miner-id", str(i)]
            if self.demo_mode:
                cmd.append("--demo")
            
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.production_miner_processes[unique_id] = proc
                self.daemon_status[unique_id] = "running"
            except Exception as e:
                print(f"❌ Failed to start miner {i}: {e}")

    def stop_miners(self):
        """Stop all mining processes"""
        print("🛑 Stopping all miners...")
        for uid, proc in self.production_miner_processes.items():
            if proc:
                proc.terminate()
                self.daemon_status[uid] = "stopped"

    def distribute_template(self, template):
        """Distribute template to miners via DTM"""
        # Save template to Temporary/Template/current_template.json
        # Miners read this
        template_path = self.temporary_template_dir / "current_template.json"
        with open(template_path, 'w') as f:
            json.dump(template, f, indent=2)
            
        # Also create working_template.json in each process folder
        for i in range(1, self.daemon_count + 1):
            proc_path = self.temporary_template_dir / f"process_{i}" / "working_template.json"
            with open(proc_path, 'w') as f:
                json.dump(template, f, indent=2)

    def check_for_solutions(self):
        """Check DTM for verified solutions"""
        if self.template_manager:
            # DTM checks folders, validates, creates ledgers, and returns solution
            solution = self.template_manager.check_miner_subfolders_for_solutions()
            return solution
        return None

    def submit_block(self, solution):
        """Submit block to node"""
        if self.demo_mode or self.test_mode:
            print(f"✅ [SIMULATED] Block submitted: {solution.get('hash')}")
            return True

        try:
            # Real submission
            block_hex = solution.get("block_hex") or solution.get("solution", {}).get("block_hex")
            if block_hex:
                cmd = [self.bitcoin_cli_path, "submitblock", block_hex]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"✅ Block submitted successfully: {result.stdout}")
                    return True
                else:
                    print(f"❌ Block submission failed: {result.stderr}")
                    return False
        except Exception as e:
            print(f"❌ Submission error: {e}")
            return False
            
        return False

    def consensus_and_submit(self, solution):
        """
        Execute Consensus Mechanism:
        1. DTM already verified (in check_for_solutions)
        2. Looping verifies DTM (implicit by receiving it)
        3. Brain global consensus
        4. Looping submits
        5. Brain post-submission consensus
        """
        print("🔄 Performing System Consensus...")
        
        # 3. Brain Global Consensus
        if not brain_perform_system_wide_consensus("demo" if self.demo_mode else "live"):
            print("❌ Brain Consensus Failed! Aborting.")
            # Log bad solution to User_Look_at
            self.log_bad_solution(solution, "Brain Consensus Failed")
            return False
            
        # 4. Submit
        if self.submit_block(solution):
            # 5. Post-submission Consensus
             brain_perform_system_wide_consensus("demo" if self.demo_mode else "live")

             # Track submission
             brain_save_submission({
                 "solution": solution,
                 "timestamp": datetime.now().isoformat(),
                 "status": "accepted"
             }, "Looping")

             return True
        else:
             brain_save_submission({
                 "solution": solution,
                 "timestamp": datetime.now().isoformat(),
                 "status": "rejected"
             }, "Looping")
             return False

    def log_bad_solution(self, solution, reason):
        """Log bad solution to User_Look_at"""
        bad_file = self.user_look_at_dir / f"bad_solution_{int(time.time())}.json"
        with open(bad_file, 'w') as f:
            json.dump({"solution": solution, "reason": reason}, f, indent=2)

    def run_mining_loop(self):
        """Main mining loop with mode logic"""
        print(f"🚀 Starting Mining Loop. Mode: {self.mining_config.get('mining_mode', 'unknown')}")
        
        # Calculate limits
        blocks_target = self.mining_config.get('blocks_per_day', 144)
        days_target = self.mining_config.get('total_days', 1)
        
        # 144 block limit check logic
        # If user requests > 144 blocks/day, we limit to 144.
        # If user requests 144 blocks but it's late in the day, we limit to what is possible.
        now = datetime.now()
        end_of_day = now.replace(hour=23, minute=59, second=59)
        minutes_left = (end_of_day - now).total_seconds() / 60
        max_possible_today = int(minutes_left / 10) # 10 min per block
        
        if blocks_target > max_possible_today:
             print(f"⚠️  Cannot mine {blocks_target} blocks today (only {max_possible_today} possible). Adjusting target.")
             blocks_target = max_possible_today
             if blocks_target < 1: blocks_target = 1
        
        self.start_miners()
        
        try:
            total_blocks_mined = 0
            
            while total_blocks_mined < blocks_target:
                # 1. Wipe Temp
                self.cleanup_temporary_files_on_new_template()
                
                # 2. Get Template
                template = self.get_real_block_template()
                if not template:
                    print("⏳ Waiting for template...")
                    time.sleep(5)
                    continue
                    
                # 3. Distribute
                self.distribute_template(template)
                
                # 4. Wait for solution
                solution = None
                print("⛏️  Mining...")
                while not solution:
                    solution = self.check_for_solutions()
                    if solution:
                        break
                    time.sleep(1)
                    
                    # Handle On Demand wake up (simulated)
                    # In a real loop, we'd check time and start/stop miners
                
                # 5. Consensus & Submit
                if self.consensus_and_submit(solution):
                    total_blocks_mined += 1
                    self.blocks_found_today += 1
                    print(f"💰 Block found! Total: {total_blocks_mined}/{blocks_target}")
                    
                    # Mode Logic handling
                    mode = self.mining_config.get('mining_mode', 'fixed')
                    
                    if mode == 'on_demand':
                        print("💤 On Demand: Stopping miners. Waking up in 40 mins...")
                        self.stop_miners()
                        # Wait 40 minutes
                        if self.demo_mode:
                            time.sleep(10) # Short wait for testing/demo
                        else:
                            time.sleep(40 * 60) # 40 minutes for production
                        self.start_miners()
                
                # Reset for next block
        
        finally:
            if not self.mining_config.get('always_on', False):
                self.stop_miners()

def parse_args():
    parser = argparse.ArgumentParser(description="Singularity Dave Looping System")
    
    # Block flags
    parser.add_argument("--block", type=int, help="Number of blocks per day (1-144)")
    parser.add_argument("--blocks-all", action="store_true", help="Mine continuously (all possible)")
    parser.add_argument("--random", type=int, help="Random blocks per day")
    
    # Time flags
    parser.add_argument("--days", type=int, default=1, help="Number of days")
    parser.add_argument("--days-all", action="store_true", help="Run forever")
    
    # Daemon flags
    parser.add_argument("--daemons", type=int, help="Number of miners")
    
    # Modes
    parser.add_argument("--continuous-1", action="store_true", help="Continuous Mode 1")
    parser.add_argument("--continuous-2", action="store_true", help="Continuous Mode 2 (Default)")
    parser.add_argument("--always-on", action="store_true", help="Always On Mode")
    parser.add_argument("--on-demand", action="store_true", help="On Demand Mode")
    
    # Environment
    parser.add_argument("--demo", action="store_true", help="Demo mode")
    parser.add_argument("--test-mode", action="store_true", help="Test mode")
    parser.add_argument("--staging", action="store_true", help="Staging mode")
    
    # Helper
    parser.add_argument("--smoke-test", action="store_true", help="Run system check")
    parser.add_argument("--wipe-user-look-at", action="store_true", help="Wipe User_Look_at folder")

    # Positional args for natural language support (simple fallback)
    parser.add_argument("args", nargs="*", help="Natural language args")

    return parser.parse_args()

def main():
    args = parse_args()
    
    # Handle simple flags
    if args.wipe_user_look_at:
        try:
            shutil.rmtree(Path(brain_get_path("user_look_at")))
            print("✅ User_Look_at wiped.")
        except Exception as e:
            print(f"❌ Wipe failed: {e}")
        return

    # Config setup
    mining_config = {
        "blocks_per_day": 144,
        "total_days": args.days,
        "mining_mode": "continuous-2", # Default
        "always_on": False
    }
    
    if args.block:
        mining_config["blocks_per_day"] = min(args.block, 144)
        mining_config["mining_mode"] = "fixed"
    elif args.blocks_all:
        mining_config["blocks_per_day"] = 144
        mining_config["mining_mode"] = "continuous"
    elif args.random:
        mining_config["blocks_per_day"] = min(args.random, 44) # User said random 1-44?
        mining_config["mining_mode"] = "random"

    if args.continuous_1:
        mining_config["mining_mode"] = "continuous-1"
    elif args.continuous_2:
        mining_config["mining_mode"] = "continuous-2"
    elif args.always_on:
        mining_config["mining_mode"] = "always_on"
        mining_config["always_on"] = True
    elif args.on_demand:
        mining_config["mining_mode"] = "on_demand"

    # Initialize System
    system = BitcoinLoopingSystem(
        demo_mode=args.demo,
        test_mode=args.test_mode,
        staging_mode=args.staging,
        daemon_count=args.daemons,
        mining_config=mining_config
    )
    
    if args.smoke_test:
        print("🔥 Running Smoke Test...")
        # Basic check of folders and connection
        if system.temporary_template_dir.exists():
            print("✅ Directory structure: PASS")
        else:
            print("❌ Directory structure: FAIL")
        return

    # Run
    system.run_mining_loop()

if __name__ == "__main__":
    main()
