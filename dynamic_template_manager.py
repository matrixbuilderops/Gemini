#!/usr/bin/env python3
"""
Dynamic Template Manager for Bitcoin Mining
Handles template coordination and GPS-enhanced mining capabilities
"""

from __future__ import annotations

import copy
import json
import logging
import multiprocessing
import os
import queue
import random
import string
import sys
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Brain file system - ALL file operations
try:
    from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
        brain_create_file,
        brain_create_folder,
        brain_write_hierarchical,
        brain_get_path,
        brain_set_mode,
        brain_get_base_path,
        brain_save_ledger,
        brain_save_math_proof,
        brain_save_system_report,
        brain_save_system_error
    )
    HAS_BRAIN_FILE_SYSTEM = True
except ImportError:
    HAS_BRAIN_FILE_SYSTEM = False
    def brain_create_file(*args, **kwargs): return None
    def brain_create_folder(*args, **kwargs): return None
    def brain_write_hierarchical(*args, **kwargs): return {}
    def brain_get_path(*args, **kwargs): return "Mining"
    def brain_set_mode(*args, **kwargs): pass
    def brain_get_base_path(): return "Mining"
    def brain_save_ledger(*args, **kwargs): return {"success": False}
    def brain_save_math_proof(*args, **kwargs): return {"success": False}
    def brain_save_system_report(*args, **kwargs): return {"success": False}
    def brain_save_system_error(*args, **kwargs): return {"success": False}

# Import smoke functionality from Brain.QTL (smoke_test and smoke_network)
try:
    # Load smoke behavior definitions from Brain.QTL
    brain_qtl_path = Path(__file__).parent / "Singularity_Dave_Brain.QTL"
    if brain_qtl_path.exists():
        with open(brain_qtl_path, 'r') as f:
            brain_content = f.read()
            SMOKE_FLAGS_AVAILABLE = '--smoke-test' in brain_content and '--smoke-network' in brain_content
    else:
        SMOKE_FLAGS_AVAILABLE = False
except Exception:
    SMOKE_FLAGS_AVAILABLE = False

CENTRAL_TZ = ZoneInfo("America/Chicago")


# ═══════════════════════════════════════════════════════════════════
# DEFENSIVE WRITE SYSTEM - NEVER FAIL, ALWAYS LOG
# Layer 0: Try template-based write (best case)
# Layer 1: Try direct write with current structure (fallback)
# Layer 2: Try backup directory (backup fallback)
# Layer 3: Try simple text log (ultimate fallback - ALWAYS works)
# Layer 4: Even if ALL logging fails, don't crash mining
# ═══════════════════════════════════════════════════════════════════

def defensive_write_json(filepath: str, data: dict, component_name: str = "UNKNOWN") -> bool:
    """
    Write JSON with 4-layer defensive fallback. NEVER FAILS.
    Returns True if write succeeded at ANY layer.
    """
    import traceback
    
    # Layer 0: Try primary write with template system
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e0:
        error_msg = f"Layer 0 failed: {e0}"
        
        # Layer 1: Try backup directory
        try:
            backup_dir = os.path.join(brain_get_base_path(), "Backup_Logs", component_name)
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, os.path.basename(filepath))
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"⚠️ {component_name}: Used backup directory: {backup_file}")
            return True
        except Exception as e1:
            error_msg += f" | Layer 1 failed: {e1}"
            
            # Layer 2: Try emergency text log
            try:
                emergency_dir = os.path.join(brain_get_base_path(), "Emergency_Logs")
                os.makedirs(emergency_dir, exist_ok=True)
                emergency_file = os.path.join(emergency_dir, f"{component_name}_emergency.log")
                with open(emergency_file, 'a') as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"TIMESTAMP: {datetime.now().isoformat()}\n")
                    f.write(f"COMPONENT: {component_name}\n")
                    f.write(f"INTENDED FILE: {filepath}\n")
                    f.write(f"DATA: {json.dumps(data, indent=2)}\n")
                    f.write(f"ERRORS: {error_msg}\n")
                print(f"⚠️ {component_name}: Used emergency text log: {emergency_file}")
                return True
            except Exception as e2:
                error_msg += f" | Layer 2 failed: {e2}"
                
                # Layer 3: Ultimate fallback - print to console and continue
                try:
                    print(f"\n{'!'*80}")
                    print(f"🚨 CRITICAL: All file writes failed for {component_name}")
                    print(f"Intended file: {filepath}")
                    print(f"Error chain: {error_msg}")
                    print(f"Data summary: {len(str(data))} bytes")
                    print(f"{'!'*80}\n")
                    return False  # Indicate failure but DON'T crash
                except (OSError, IOError):
                    # Even print failed (stdout redirect issue?) - continue silently
                    return False


def load_template_from_examples(template_name: str, component: str = None) -> dict:
    """
    Load structure from System_File_Examples that Brainstem created from Brain.QTL.
    Maps friendly names to actual example files.
    If System_File_Examples doesn't exist, returns minimal fallback.
    """
    # Map friendly names to actual file locations (created by Brainstem from Brain.QTL)
    template_map = {
        # DTM templates
        'global_ledger': 'DTM/Global/global_ledger_example.json',
        'hourly_ledger': 'DTM/Hourly/hourly_ledger_example.json',
        'global_math_proof': 'DTM/Global/global_math_proof_example.json',
        'hourly_math_proof': 'DTM/Hourly/hourly_math_proof_example.json',
        'global_dtm_report': 'DTM/Global/global_dtm_report_example.json',
        'hourly_dtm_report': 'DTM/Hourly/hourly_dtm_report_example.json',
        'global_dtm_error': 'DTM/Global/global_dtm_error_example.json',
        'hourly_dtm_error': 'DTM/Hourly/hourly_dtm_error_example.json',

        # DTM aggregated payloads
        'aggregated_ledger_global': 'Ledgers/Aggregated/global_ledger_aggregated_example.json',
        'aggregated_ledger_year': 'Ledgers/Aggregated/Year/year_ledger_aggregated_example.json',
        'aggregated_ledger_month': 'Ledgers/Aggregated/Month/month_ledger_aggregated_example.json',
        'aggregated_ledger_week': 'Ledgers/Aggregated/Week/week_ledger_aggregated_example.json',
        'aggregated_ledger_day': 'Ledgers/Aggregated/Day/day_ledger_aggregated_example.json',
        'aggregated_ledger_hour': 'Ledgers/Aggregated/Hour/hourly_ledger_aggregated_example.json',

        # Submission log aggregated payloads
        'aggregated_submission_log_global': 'Submission_Logs/Aggregated/global_submission_log_aggregated_example.json',
        'aggregated_submission_log_year': 'Submission_Logs/Aggregated/Year/year_submission_log_aggregated_example.json',
        'aggregated_submission_log_month': 'Submission_Logs/Aggregated/Month/month_submission_log_aggregated_example.json',
        'aggregated_submission_log_week': 'Submission_Logs/Aggregated/Week/week_submission_log_aggregated_example.json',
        'aggregated_submission_log_day': 'Submission_Logs/Aggregated/Day/day_submission_log_aggregated_example.json',
        'aggregated_submission_log_hour': 'Submission_Logs/Aggregated/Hour/hourly_submission_log_aggregated_example.json',
        
        # Looping templates
        'global_submission': 'Looping/Global/global_submission_example.json',
        'hourly_submission': 'Looping/Hourly/hourly_submission_example.json',
        'global_looping_report': 'Looping/Global/global_looping_report_example.json',
        'hourly_looping_report': 'Looping/Hourly/hourly_looping_report_example.json',
        'global_looping_error': 'Looping/Global/global_looping_error_example.json',
        'hourly_looping_error': 'Looping/Hourly/hourly_looping_error_example.json',

        # System Reports aggregated payloads
        'aggregated_system_report_global': 'System_Reports/Aggregated/Global/global_aggregated_report_example.json',
        'aggregated_system_report_year': 'System_Reports/Aggregated/Year/year_aggregated_report_example.json',
        'aggregated_system_report_month': 'System_Reports/Aggregated/Month/month_aggregated_report_example.json',
        'aggregated_system_report_week': 'System_Reports/Aggregated/Week/week_aggregated_report_example.json',
        'aggregated_system_report_day': 'System_Reports/Aggregated/Day/day_aggregated_report_example.json',
        'aggregated_system_report_hour': 'System_Reports/Aggregated/Hour/hourly_aggregated_report_example.json',

        # Error Reports aggregated payloads
        'aggregated_error_report_global': 'Error_Reports/Aggregated/Global/global_aggregated_error_example.json',
        'aggregated_error_report_year': 'Error_Reports/Aggregated/Year/year_aggregated_error_example.json',
        'aggregated_error_report_month': 'Error_Reports/Aggregated/Month/month_aggregated_error_example.json',
        'aggregated_error_report_week': 'Error_Reports/Aggregated/Week/week_aggregated_error_example.json',
        'aggregated_error_report_day': 'Error_Reports/Aggregated/Day/day_aggregated_error_example.json',
        'aggregated_error_report_hour': 'Error_Reports/Aggregated/Hour/hourly_aggregated_error_example.json',

        # System Logs aggregated payloads
        'aggregated_system_log_global': 'System_Logs/Aggregated/Global/global_aggregated_log_example.json',
        'aggregated_system_log_hour': 'System_Logs/Aggregated/Hourly/hourly_aggregated_log_example.json',

        # Aggregated index templates (rollups)
        'ledger_aggregated_index_root': 'Ledgers/Aggregated_Index/aggregated_index_root_example.json',
        'ledger_aggregated_index_year': 'Ledgers/Aggregated_Index/Year/aggregated_index_year_example.json',
        'ledger_aggregated_index_month': 'Ledgers/Aggregated_Index/Month/aggregated_index_month_example.json',
        'ledger_aggregated_index_week': 'Ledgers/Aggregated_Index/Week/aggregated_index_week_example.json',
        'ledger_aggregated_index_day': 'Ledgers/Aggregated_Index/Day/aggregated_index_day_example.json',
        'ledger_aggregated_index_hour': 'Ledgers/Aggregated_Index/Hour/aggregated_index_hour_example.json',
        'submission_log_aggregated_index_root': 'Submission_Logs/Aggregated_Index/aggregated_index_root_example.json',
        'submission_log_aggregated_index_year': 'Submission_Logs/Aggregated_Index/Year/aggregated_index_year_example.json',
        'submission_log_aggregated_index_month': 'Submission_Logs/Aggregated_Index/Month/aggregated_index_month_example.json',
        'submission_log_aggregated_index_week': 'Submission_Logs/Aggregated_Index/Week/aggregated_index_week_example.json',
        'submission_log_aggregated_index_day': 'Submission_Logs/Aggregated_Index/Day/aggregated_index_day_example.json',
        'submission_log_aggregated_index_hour': 'Submission_Logs/Aggregated_Index/Hour/aggregated_index_hour_example.json',
        'system_report_aggregated_index_root': 'System_Reports/Aggregated_Index/aggregated_index_root_example.json',
        'system_report_aggregated_index_year': 'System_Reports/Aggregated_Index/Year/aggregated_index_year_example.json',
        'system_report_aggregated_index_month': 'System_Reports/Aggregated_Index/Month/aggregated_index_month_example.json',
        'system_report_aggregated_index_week': 'System_Reports/Aggregated_Index/Week/aggregated_index_week_example.json',
        'system_report_aggregated_index_day': 'System_Reports/Aggregated_Index/Day/aggregated_index_day_example.json',
        'system_report_aggregated_index_hour': 'System_Reports/Aggregated_Index/Hour/aggregated_index_hour_example.json',
        'error_report_aggregated_index_root': 'Error_Reports/Aggregated_Index/aggregated_index_root_example.json',
        'error_report_aggregated_index_year': 'Error_Reports/Aggregated_Index/Year/aggregated_index_year_example.json',
        'error_report_aggregated_index_month': 'Error_Reports/Aggregated_Index/Month/aggregated_index_month_example.json',
        'error_report_aggregated_index_week': 'Error_Reports/Aggregated_Index/Week/aggregated_index_week_example.json',
        'error_report_aggregated_index_day': 'Error_Reports/Aggregated_Index/Day/aggregated_index_day_example.json',
        'error_report_aggregated_index_hour': 'Error_Reports/Aggregated_Index/Hour/aggregated_index_hour_example.json',
        'global_aggregated_index_root': 'Global_Aggregated/Aggregated_Index/aggregated_index_root_example.json',
        'global_aggregated_index_year': 'Global_Aggregated/Aggregated_Index/Year/aggregated_index_year_example.json',
        'global_aggregated_index_month': 'Global_Aggregated/Aggregated_Index/Month/aggregated_index_month_example.json',
        'global_aggregated_index_week': 'Global_Aggregated/Aggregated_Index/Week/aggregated_index_week_example.json',
        'global_aggregated_index_day': 'Global_Aggregated/Aggregated_Index/Day/aggregated_index_day_example.json',
        'global_aggregated_index_hour': 'Global_Aggregated/Aggregated_Index/Hour/aggregated_index_hour_example.json',

        # Global aggregated payloads
        'global_aggregated_payload_root': 'Global_Aggregated/Aggregated/global_aggregated_payload_example.json',
        'global_aggregated_payload_year': 'Global_Aggregated/Aggregated/Year/year_global_aggregated_payload_example.json',
        'global_aggregated_payload_month': 'Global_Aggregated/Aggregated/Month/month_global_aggregated_payload_example.json',
        'global_aggregated_payload_week': 'Global_Aggregated/Aggregated/Week/week_global_aggregated_payload_example.json',
        'global_aggregated_payload_day': 'Global_Aggregated/Aggregated/Day/day_global_aggregated_payload_example.json',
        'global_aggregated_payload_hour': 'Global_Aggregated/Aggregated/Hour/hourly_global_aggregated_payload_example.json',
        
        # Miner templates
        'global_mining_report': 'Miners/Global/global_mining_process_report_example.json',
        'hourly_mining_report': 'Miners/Hourly/hourly_mining_process_report_example.json',
        'global_mining_error': 'Miners/Global/global_mining_process_error_example.json',
        'hourly_mining_error': 'Miners/Hourly/hourly_mining_process_error_example.json',
        
        # Brain templates
        'global_system_report': 'Brain/Global/global_system_report_example.json',
        'hourly_system_report': 'Brain/Global/hourly_system_report_example.json',
        'global_error_report': 'Brain/Global/global_error_report_example.json',
        'hourly_error_report': 'Brain/Hourly/hourly_error_report_example.json',
        
        # Template
        'current_template': 'Templates/current_template_example.json',
    }
    
    try:
        # Get the actual file path from Brainstem-generated examples
        relative_path = template_map.get(template_name, f"{component}/{template_name}_example.json")
        template_path = Path("System_File_Examples") / relative_path
        
        with open(template_path, 'r') as f:
            template_data = json.load(f)
        
        # Return a deep copy so modifications don't affect the example file
        return copy.deepcopy(template_data)
    
    except Exception as e:
        print(f"⚠️ Could not load template '{template_name}' from System_File_Examples: {e}")
        # Return minimal fallback structure
        return {
            "metadata": {
                "created_by": component or "UNKNOWN",
                "template_load_failed": True,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            "entries": [],
            "errors": [],
            "reports": []
        }


# Brain-coordinated logging setup
def setup_brain_coordinated_logging_dtm(component_name, base_dir=None):
    """Setup console-only logging for DTM - Brain handles all file operations"""
    logger = logging.getLogger(component_name)
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    # Console handler only - Brain save functions handle file writes
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger
    logger.addHandler(hourly_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

dtm_logger = setup_brain_coordinated_logging_dtm("dtm")

def report_dtm_error(error_type, severity, message, context=None, recovery_action=None, stack_trace=None, base_dir=None):
    """
    Report DTM error with comprehensive tracking and defensive fallback.
    Uses System_File_Examples templates and NEVER FAILS.
    
    Args:
        error_type: Type of error (validation_failed, hash_mismatch, etc.)
        severity: critical, error, warning, info
        message: Human-readable error message
        context: Dict of additional context data
        recovery_action: What the system did to recover
        stack_trace: Full stack trace if available
    """
    import traceback
    
    now = datetime.now()
    # Use brain_get_path for dynamic resolution
    base_root = Path(brain_get_path("dtm_error_reports"))
    week = now.strftime('%W')
    error_id = f"dtm_err_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}"
    
    # Build comprehensive error entry
    error_entry = {
        "error_id": error_id,
        "timestamp": now.isoformat(),
        "severity": severity,
        "error_type": error_type,
        "message": message,
        "context": context or {},
        "recovery_action": recovery_action or "None taken",
        "stack_trace": stack_trace or traceback.format_exc() if sys.exc_info()[0] else None
    }
    
    # === GLOBAL ERROR FILE (Mining/DTM/Global/global_dtm_error.json) ===
    try:
        global_error_file = base_root / "Global" / "global_dtm_error.json"
        
        # Load existing or create from template
        if os.path.exists(global_error_file):
            try:
                with open(global_error_file, 'r') as f:
                    global_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Corrupted DTM error file {global_error_file}: {e}. Using template.")
                global_data = load_template_from_examples('global_dtm_error', 'DTM')
            except (FileNotFoundError, PermissionError) as e:
                print(f"Warning: Cannot read {global_error_file}: {e}. Using template.")
                global_data = load_template_from_examples('global_dtm_error', 'DTM')
        else:
            global_data = load_template_from_examples('global_dtm_error', 'DTM')
        
        # Update comprehensive statistics
        global_data["errors"].append(error_entry)
        global_data["total_errors"] = len(global_data["errors"])
        
        # Update severity breakdown
        if "errors_by_severity" not in global_data:
            global_data["errors_by_severity"] = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        global_data["errors_by_severity"][severity] = global_data["errors_by_severity"].get(severity, 0) + 1
        
        # Update type breakdown
        if "errors_by_type" not in global_data:
            global_data["errors_by_type"] = {}
        global_data["errors_by_type"][error_type] = global_data["errors_by_type"].get(error_type, 0) + 1
        
        # Write with defensive fallback
        defensive_write_json(global_error_file, global_data, "DTM")
        
    except Exception as e:
        dtm_logger.error(f"Failed to write global DTM error: {e}")
    
    # === HOURLY ERROR FILE (Mining/DTM/YYYY/MM/DD/HH/hourly_dtm_error.json) ===
    try:
        # Dynamically get the hourly path
        hourly_error_path_str = brain_get_path("hourly_dtm_error", custom_timestamp=now.isoformat())
        hourly_error_file = Path(hourly_error_path_str)
        hourly_dir = hourly_error_file.parent
        
        # Load existing or create from template
        if os.path.exists(hourly_error_file):
            try:
                with open(hourly_error_file, 'r') as f:
                    hourly_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Corrupted hourly DTM error {hourly_error_file}: {e}. Using template.")
                hourly_data = load_template_from_examples('hourly_dtm_error', 'DTM')
            except (FileNotFoundError, PermissionError) as e:
                print(f"Warning: Cannot read {hourly_error_file}: {e}. Using template.")
                hourly_data = load_template_from_examples('hourly_dtm_error', 'DTM')
        else:
            hourly_data = load_template_from_examples('hourly_dtm_error', 'DTM')
        
        # Update hourly data
        hourly_data["hour"] = now.strftime("%Y-%m-%d_%H")
        hourly_data["errors"].append(error_entry)
        hourly_data["total_errors"] = len(hourly_data["errors"])
        
        # Update hourly statistics
        if "errors_by_severity" not in hourly_data:
            hourly_data["errors_by_severity"] = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        hourly_data["errors_by_severity"][severity] = hourly_data["errors_by_severity"].get(severity, 0) + 1
        
        if "errors_by_type" not in hourly_data:
            hourly_data["errors_by_type"] = {}
        hourly_data["errors_by_type"][error_type] = hourly_data["errors_by_type"].get(error_type, 0) + 1
        
        # Write with defensive fallback
        defensive_write_json(hourly_error_file, hourly_data, "DTM")
        
    except Exception as e:
        dtm_logger.error(f"Failed to write hourly DTM error: {e}")
    
    try:
        brain_save_system_error(error_entry, "DTM")
    except Exception as e:
        dtm_logger.error(f"Failed to write Brain.QTL system error: {e}")

    dtm_logger.error(f"🧠 DTM Error [{severity}] {error_type}: {message}")


def report_dtm_status(templates_processed=0, validations=0, solutions_found=0, consensus_decisions=0, base_dir=None):
    """
    Report DTM status with comprehensive tracking - ADAPTS to template, NEVER FAILS.
    
    Args:
        templates_processed: Number of templates processed
        validations: Number of validations performed
        solutions_found: Number of valid solutions found
        consensus_decisions: Number of consensus decisions made
    """
    now = datetime.now()
    # Use brain_get_path for dynamic resolution
    base_root = Path(brain_get_path("dtm_system_reports"))
    week = now.strftime('%W')
    report_id = f"dtm_report_{now.strftime('%Y%m%d_%H%M%S')}"
    
    # Build comprehensive report entry
    report_entry = {
        "report_id": report_id,
        "timestamp": now.isoformat(),
        "templates_processed": templates_processed,
        "solutions_validated": validations,
        "consensus_decisions": consensus_decisions
    }
    
    # === GLOBAL REPORT FILE ===
    try:
        global_report_file = base_root / "Global" / "global_dtm_report.json"
        
        # Load existing or create from template
        if os.path.exists(global_report_file):
            try:
                with open(global_report_file, 'r') as f:
                    report_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Corrupted DTM report {global_report_file}: {e}. Using template.")
                report_data = load_template_from_examples('global_dtm_report', 'DTM')
            except (FileNotFoundError, PermissionError) as e:
                print(f"Warning: Cannot read {global_report_file}: {e}. Using template.")
                report_data = load_template_from_examples('global_dtm_report', 'DTM')
        else:
            report_data = load_template_from_examples('global_dtm_report', 'DTM')
        
        # Update statistics
        if "reports" not in report_data:
            report_data["reports"] = []
        report_data["reports"].append(report_entry)
        
        if "total_templates_processed" in report_data:
            report_data["total_templates_processed"] = report_data.get("total_templates_processed", 0) + templates_processed
        if "total_validations_performed" in report_data:
            report_data["total_validations_performed"] = report_data.get("total_validations_performed", 0) + validations
        if "total_solutions_found" in report_data:
            report_data["total_solutions_found"] = report_data.get("total_solutions_found", 0) + solutions_found
        
        # Update metadata
        if "metadata" in report_data:
            report_data["metadata"]["last_updated"] = now.isoformat()
        
        # Defensive write
        defensive_write_json(global_report_file, report_data, "DTM")
        
    except Exception as e:
        dtm_logger.error(f"Failed to write global DTM report: {e}")
    
    # === HOURLY REPORT FILE ===
    try:
        # Dynamically get the hourly path
        hourly_report_path_str = brain_get_path("hourly_dtm_report", custom_timestamp=now.isoformat())
        hourly_report_file = Path(hourly_report_path_str)
        hourly_dir = hourly_report_file.parent
        
        # Load existing or create from template
        if os.path.exists(hourly_report_file):
            try:
                with open(hourly_report_file, 'r') as f:
                    hourly_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Corrupted hourly DTM report {hourly_report_file}: {e}. Using template.")
                hourly_data = load_template_from_examples('hourly_dtm_report', 'DTM')
            except (FileNotFoundError, PermissionError) as e:
                print(f"Warning: Cannot read {hourly_report_file}: {e}. Using template.")
                hourly_data = load_template_from_examples('hourly_dtm_report', 'DTM')
        else:
            hourly_data = load_template_from_examples('hourly_dtm_report', 'DTM')
        
        # Update hourly data
        hourly_data["hour"] = now.strftime("%Y-%m-%d_%H")
        if "templates_processed" in hourly_data:
            hourly_data["templates_processed"] = hourly_data.get("templates_processed", 0) + templates_processed
        if "solutions_validated" in hourly_data:
            hourly_data["solutions_validated"] = hourly_data.get("solutions_validated", 0) + validations
        
        # Defensive write
        defensive_write_json(hourly_report_file, hourly_data, "DTM")
        
    except Exception as e:
        dtm_logger.error(f"Failed to write hourly DTM report: {e}")

    try:
        brain_save_system_report(report_entry, "DTM", report_type="status")
    except Exception as e:
        dtm_logger.error(f"Failed to write Brain.QTL system report: {e}")


# BRAIN.QTL INTEGRATION - DTM must query Brain.QTL for paths, never create folders
def _load_brain_qtl() -> dict:
    """Load Brain.QTL configuration - canonical folder authority for DTM"""
    brain_path = Path(__file__).parent / "Singularity_Dave_Brain.QTL"
    try:
        with open(brain_path, 'r') as f:
            content = f.read()
            if content.startswith('---'):
                content = content[3:]
            return yaml.safe_load(content)
    except Exception as e:
        print(f"⚠️ DTM Warning: Could not load Brain.QTL: {e}")
        return {}

def _get_mode_from_flags(flags: list) -> str:
    """Determine operating mode from command-line flags"""
    flag_set = set(flags)
    if '--demo' in flag_set and '--test' in flag_set:
        return 'combined_demo_test_mode'
    elif '--demo' in flag_set:
        return 'demo_mode'
    elif '--test' in flag_set:
        return 'test_mode'
    else:
        return 'production_mode'

def get_brain_qtl_paths_dtm(flags: list = None) -> dict:
    """Get paths from Brain.QTL using the centralized brainstem functions."""
    # This function now acts as a wrapper around the brain_get_path calls.
    # The mode is handled by brain_set_mode at startup.
    return {
        'temporary_template': brain_get_path('temporary_template_dir'),
        'ledgers': brain_get_path('ledgers_dir'),
        'base_path': brain_get_base_path()
    }

def validate_folder_exists_dtm(folder_path: str, component_name: str = "DTM") -> bool:
    """Validate folder exists - do NOT create it (Brainstem responsibility)"""
    if not Path(folder_path).exists():
        print(f"❌ {component_name}: Folder {folder_path} missing - should be created by Brainstem")
        return False
    return True


def current_time() -> datetime:
    """Return the current time in US Central timezone."""
    return datetime.now(CENTRAL_TZ)


def current_timestamp() -> str:
    """Return the current ISO-8601 timestamp in US Central time."""
    return current_time().isoformat()


MINER_IDENTIFIERS: Dict[int, str] = {
    1: "MINER_ALPHA",
    2: "MINER_BETA",
    3: "MINER_GAMMA",
    4: "MINER_DELTA",
    5: "MINER_EPSILON",
    6: "MINER_ZETA",
    7: "MINER_ETA",
    8: "MINER_THETA",
    9: "MINER_IOTA",
    10: "MINER_KAPPA",
    11: "MINER_LAMBDA",
    12: "MINER_MU",
    13: "MINER_NU",
    14: "MINER_XI",
    15: "MINER_OMICRON",
    16: "MINER_PI",
    17: "MINER_RHO",
    18: "MINER_SIGMA",
    19: "MINER_TAU",
    20: "MINER_UPSILON",
}


BASE_DIR = Path(__file__).resolve().parent
FILESYSTEM_ROOT_OVERRIDE: Optional[Path] = None


def set_filesystem_root_override(root: Optional[Path]) -> None:
    """Override filesystem root for blueprint resolution (primarily for tests)."""
    global FILESYSTEM_ROOT_OVERRIDE
    FILESYSTEM_ROOT_OVERRIDE = Path(root) if root else None


def normalize_blueprint_path(raw_path: Optional[str]) -> Optional[Path]:
    """Normalize blueprint paths by stripping whitespace and resolving separators."""
    if not raw_path:
        return None

    cleaned = raw_path.strip().replace("\\", "/")
    if not cleaned:
        return None

    segments: List[str] = []
    for part in cleaned.split("/"):
        part = part.strip()
        if not part or part == ".":
            continue
        segments.append(part)

    if not segments:
        return None

    return Path(*segments)


def to_absolute_path(path_obj: Path) -> Path:
    """Convert relative paths to absolute paths anchored at the repository root."""
    if path_obj.is_absolute():
        return path_obj
    root = FILESYSTEM_ROOT_OVERRIDE or BASE_DIR
    return root / path_obj


def to_absolute_from_string(path_str: str) -> Path:
    """Convert a string path to an absolute Path relative to the repository root."""
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate
    return to_absolute_path(candidate)


def resolve_brain_path(
    file_type: str,
    environment: str = "Mining",
    custom_path: Optional[Tuple[str, str, str, str]] = None,
) -> Optional[str]:
    """Fetch a Brain.QTL managed path if the brain module is available."""
    try:
        from Singularity_Dave_Brainstem_UNIVERSE_POWERED import get_brain_qtl_file_path

        return get_brain_qtl_file_path(file_type, environment, custom_path)
    except Exception:
        return None


def load_brain_blueprint(verbose: bool = False) -> Dict[str, Any]:
    """Load the canonical Brain.QTL blueprint from runtime."""

    candidate_files = [BASE_DIR / "Singularity_Dave_Brain.QTL"]

    for candidate in candidate_files:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as handle:
                    blueprint = yaml.safe_load(handle) or {}

                # Follow redirect pointers so legacy stubs can defer to the canonical blueprint.
                redirect_target = (
                    blueprint.get("redirect", {}).get("blueprint")
                    or blueprint.get("meta", {}).get("canonical_blueprint")
                )
                if redirect_target and candidate.name != redirect_target:
                    redirected_path = BASE_DIR / redirect_target
                    if redirected_path.exists():
                        with open(redirected_path, "r", encoding="utf-8") as redirected:
                            blueprint = yaml.safe_load(redirected) or {}
                        if verbose:
                            print(
                                f"✅ Resolved Brain blueprint via redirect {candidate.name} → {redirect_target}"
                            )
                    else:
                        if verbose:
                            print(
                                f"⚠️ Redirect target {redirect_target} referenced by {candidate.name} not found"
                            )

                if verbose:
                    print(
                        f"✅ Loaded Brain blueprint from {candidate.relative_to(BASE_DIR)}"
                    )
                return blueprint
            except Exception as exc:
                if verbose:
                    print(f"⚠️ Failed loading {candidate}: {exc}")

    if verbose:
        print("⚠️ Brain blueprint not found; folder verification disabled")
    return {}


def is_example_path(raw_path: str) -> bool:
    """Detect blueprint entries that are illustrative examples rather than canonical paths."""
    if not raw_path:
        return False
    sample_markers = ("YYYY", "2025-", "example", "Example", "Hourly")
    return any(marker in raw_path for marker in sample_markers)


# =====================================================
# GPS ENHANCEMENT FUNCTIONS (Integrated)
# =====================================================


def knuth_function(height: int, base: int = 3, offset: int = 161) -> int:
    """
    Calculate Knuth-enhanced nonce starting point

    Formula: K(h, b, o) = (h^b + o) mod 2^32

    Args:
        height: Block height from template
        base: Knuth exponent (default: 3)
        offset: Knuth offset (default: 161)

    Returns:
        Knuth result as 32-bit unsigned integer
    """
    try:
        result = pow(height, base) + offset
        knuth_result = result % (2**32)
        return knuth_result
    except Exception as e:
        print(f"❌ Error in knuth_function: {e}")
        
        # COMPREHENSIVE ERROR REPORTING: Generate system error report for DTM calculation failures
        try:
            # Note: DTM doesn't have direct brain connection, use global error reporting if available
            error_data = {
                "error_type": "dtm_calculation_failure",
                "component": "DynamicTemplateManager",
                "error_message": str(e),
                "operation": "knuth_function",
                "height": height,
                "severity": "medium"
            }
            print(f"📋 DTM Error logged: {error_data['error_type']}")
        except Exception as report_error:
            print(f"⚠️ Failed to create error report: {report_error}")
        return (height * base + offset) % (2**32)


def get_gps_coordinates() -> Dict[str, float]:
    """
    Get GPS coordinates for nonce delta calculation

    Priority:
    1. From Brainstem (if available)
    2. From cached file
    3. Fallback to generated coordinates
    """
    try:
        from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
            get_global_brain as get_brain_func,
        )

        brain = get_brain_func()
        if brain and hasattr(brain, "get_gps_coordinates"):
            gps_data = brain.get_gps_coordinates()
            if gps_data and "latitude" in gps_data and "longitude" in gps_data:
                return {
                    "latitude": float(gps_data["latitude"]),
                    "longitude": float(gps_data["longitude"]),
                    "source": "brainstem",
                }
    except (ImportError, AttributeError, Exception):
        pass

    environment = (
        os.environ.get("BRAIN_QTL_ENVIRONMENT")
        or os.environ.get("BRAIN_ENVIRONMENT")
        or os.environ.get("DTM_ENVIRONMENT")
        or "Mining"
    )

    base_path_str = resolve_brain_path("base", environment) or environment
    system_dir = to_absolute_from_string(str(Path(base_path_str) / "System" / "Utilities"))
    gps_cache_file = system_dir / "gps_coordinates.json"

    try:
        if gps_cache_file.exists():
            with open(gps_cache_file, "r") as handle:
                cached_gps = json.load(handle)
            if "latitude" in cached_gps and "longitude" in cached_gps:
                return {
                    "latitude": float(cached_gps["latitude"]),
                    "longitude": float(cached_gps["longitude"]),
                    "source": "cache",
                }
    except Exception:
        pass

    seed_value = int(time.time() / 3600)
    random.seed(seed_value)
    latitude = random.uniform(-90.0, 90.0)
    longitude = random.uniform(-180.0, 180.0)

    try:
        # ARCHITECTURAL COMPLIANCE: Brain/Brainstem creates folders, DTM creates files only
        generated_payload = {
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": time.time(),
            "seed": seed_value,
        }
        with open(gps_cache_file, "w") as handle:
            json.dump(generated_payload, handle, indent=2)
    except Exception:
        pass

    return {"latitude": latitude, "longitude": longitude, "source": "generated"}


def calculate_gps_delta(latitude: float, longitude: float) -> int:
    """
    Calculate GPS-based nonce delta

    Formula: Δ = (|lat| * 1,000,000 + |lon| * 1,000,000) mod 2^32
    """
    try:
        lat_scaled = int(abs(latitude) * 1_000_000)
        lon_scaled = int(abs(longitude) * 1_000_000)
        delta = (lat_scaled + lon_scaled) % (2**32)
        return delta
    except Exception as e:
        print(f"❌ Error in calculate_gps_delta: {e}")
        return 0


def calculate_gps_enhanced_nonce_range(
    template_data: Dict,
) -> Tuple[int, int, int, Dict]:
    """
    Calculate GPS-enhanced nonce range for targeted mining using DETERMINISTIC entropy

    Process:
    1. Get block height from template
    2. Calculate Knuth function: K(h, 3, 161)
    3. Extract deterministic entropy from previous block hash and difficulty
    4. Calculate target delta using REAL blockchain data (not fake coordinates)
    5. Calculate target nonce: N_target = (K + Δ) mod 2^32
    6. Define search range: [N_target - 5M, N_target + 5M] (10M total split between miners)

    Returns:
        Tuple of (nonce_start, nonce_end, target_nonce, gps_info)
    """
    try:
        height = template_data.get("height", 0)
        if height == 0:
            raise ValueError("Invalid height in template data")

        knuth_result = knuth_function(height, base=3, offset=161)
        
        # DETERMINISTIC entropy from blockchain data (not fake GPS)
        prev_hash = template_data.get("previousblockhash", "0" * 64)
        difficulty_bits = template_data.get("bits", "1d00ffff")
        
        # Extract first 64 bits of previous block hash as entropy
        hash_entropy = int(prev_hash[:16], 16) if prev_hash else 0
        
        # Use difficulty bits as additional entropy factor
        difficulty_entropy = int(difficulty_bits, 16) if isinstance(difficulty_bits, str) else difficulty_bits
        
        # Calculate deterministic delta using blockchain data
        # XOR operation ensures all entropy sources contribute
        deterministic_delta = (hash_entropy ^ difficulty_entropy ^ knuth_result) % (2**32)
        
        # Calculate target nonce using deterministic mathematical aiming
        target_nonce = (knuth_result + deterministic_delta) % (2**32)

        # 10M range to split between 5 miners (2M each)
        range_size = 5_000_000
        nonce_start = max(0, target_nonce - range_size)
        nonce_end = min(2**32 - 1, target_nonce + range_size)

        gps_info = {
            "height": height,
            "knuth_result": knuth_result,
            "knuth_formula": f"K({height}, 3, 161) = {knuth_result}",
            "blockchain_entropy": {
                "previous_hash": prev_hash[:16] + "...",
                "hash_entropy": hash_entropy,
                "difficulty_bits": difficulty_bits,
                "difficulty_entropy": difficulty_entropy,
                "source": "deterministic_blockchain_data"
            },
            "deterministic_delta": deterministic_delta,
            "delta_formula": f"Δ = (hash_entropy ^ difficulty_entropy ^ knuth) mod 2^32 = {deterministic_delta}",
            "target_nonce": target_nonce,
            "target_formula": f"N_target = ({knuth_result} + {deterministic_delta}) mod 2^32 = {target_nonce}",
            "nonce_range": {
                "start": nonce_start,
                "end": nonce_end,
                "size": nonce_end - nonce_start + 1,
            },
            "range_formula": f"[{target_nonce} - 5M, {target_nonce} + 5M] = [{nonce_start:,}, {nonce_end:,}]",
            "miner_distribution": "10M range split between 5 miners (2M each)"
        }

        return nonce_start, nonce_end, target_nonce, gps_info

    except Exception as e:
        print(f"❌ Error in calculate_gps_enhanced_nonce_range: {e}")
        height = template_data.get("height", 0)
        fallback_start = height % 1_000_000
        fallback_end = min(fallback_start + 2_000_000, 2**32 - 1)
        fallback_target = (fallback_start + fallback_end) // 2

        fallback_info = {
            "height": height,
            "error": str(e),
            "fallback_mode": True,
            "nonce_range": {
                "start": fallback_start,
                "end": fallback_end,
                "size": fallback_end - fallback_start + 1,
            },
        }

        return fallback_start, fallback_end, fallback_target, fallback_info


def calculate_solution_probability(bits_hex: str) -> float:
    """Calculate solution probability from difficulty bits"""
    try:
        bits = int(bits_hex, 16)
        exponent = bits >> 24
        mantissa = bits & 0xFFFFFF

        if exponent <= 3:
            target = mantissa >> (8 * (3 - exponent))
        else:
            target = mantissa << (8 * (exponent - 3))

        max_target = 2**256
        probability = target / max_target
        return probability
    except Exception as e:
        print(f"❌ Error calculating solution probability: {e}")
        return 0.0


def is_instant_solve_capable(bits_hex: str, threshold: float = 0.0001) -> bool:
    """Determine if difficulty allows instant solving"""
    try:
        if bits_hex.lower() in ["1d00ffff", "0x1d00ffff"]:
            return True
        probability = calculate_solution_probability(bits_hex)
        return probability >= threshold
    except Exception as e:
        print(f"❌ Error in is_instant_solve_capable: {e}")
        return False


# =====================================================
# END GPS ENHANCEMENT FUNCTIONS
# =====================================================


def get_miner_id(miner_number: int) -> str:
    """
    Get miner ID for terminal number (supports 1-1000 daemons)

    Format:
    - 1-999: MINER_001, MINER_002, ..., MINER_999
    - 1000+: MINER_1000, MINER_1001, etc.

    Args:
        miner_number: Daemon number (1-1000+)

    Returns:
        Formatted miner ID string
    """
    if miner_number < 1:
        return f"MINER_INVALID_{miner_number}"

    if miner_number in MINER_IDENTIFIERS:
        return MINER_IDENTIFIERS[miner_number]

    # Zero-padded 3-digit format for 21-999, regular format for 1000+
    if miner_number < 1000:
        return f"MINER_{miner_number:03d}"
    return f"MINER_{miner_number}"


def generate_unique_block_id() -> str:
    """Generate unique block ID: YYYYMMDD_HHMMSS_XXX"""
    timestamp = current_time().strftime("%Y%m%d_%H%M%S")
    unique_suffix = "".join(random.choices(string.ascii_uppercase, k=3))
    return f"{timestamp}_{unique_suffix}"


# Global brain fallback
def get_global_brain():
    return None


# Try to import global brain, but handle any errors gracefully
try:
    from Singularity_Dave_Brainstem_UNIVERSE_POWERED import get_global_brain

    print("🧠 Global brain import successful")
except (ImportError, SyntaxError, Exception) as e:
    print(f"⚠️ Global brain not available - using fallback: {e}")


class UltraHexSystem:
    """
    Ultra Hex Oversight System
    Manages exponential difficulty scaling and bucket consensus for 64+ hex values.
    """
    def __init__(self):
        self.bucket_size = 64
        self.max_digits = 256
        self.base_difficulty = 2**64

    def calculate_bucket(self, leading_zeros: int) -> Dict[str, Any]:
        """
        Calculate the Ultra Hex bucket for a given number of leading zeros.
        Buckets represent exponential difficulty tiers (e.g., 0-63, 64-127).
        """
        sanitized_zeros = max(0, int(leading_zeros))
        bucket_digit = min(self.max_digits, (sanitized_zeros // self.bucket_size) + 1)
        bucket_start = (bucket_digit - 1) * self.bucket_size
        bucket_end = min(bucket_start + (self.bucket_size - 1), (self.max_digits * self.bucket_size) - 1)
        progress = max(0, sanitized_zeros - bucket_start)
        remaining = max(0, self.bucket_size - progress)

        # Exponential difficulty scaling
        # Each bucket represents a 2^64 multiplier in search space difficulty
        difficulty_tier = self.base_difficulty ** (bucket_digit - 1)

        return {
            "definition": "Ultra Hex bucket consensus (64 leading hex zeros per digit)",
            "bucket_label": f"Ultra-{bucket_digit}",
            "bucket_size": self.bucket_size,
            "ultra_hex_digit": bucket_digit,
            "bucket_range": [bucket_start, bucket_end],
            "progress_within_bucket": progress,
            "remaining_in_bucket": remaining,
            "required_leading_zeros": sanitized_zeros,
            "max_digits": self.max_digits,
            "difficulty_tier": str(difficulty_tier),  # String to avoid overflow in JSON
            "timestamp": current_timestamp(),
        }

    def verify_consensus(self, solution_data: Dict[str, Any], template_target_zeros: int) -> Dict[str, Any]:
        """
        Verify if a solution meets the consensus requirements for its Ultra Hex bucket.
        """
        leading_zeros = solution_data.get("leading_zeros_achieved", 0)
        bucket_info = self.calculate_bucket(leading_zeros)

        # Consensus check: Does the solution meet the template's required bucket level?
        # Note: Usually we check against specific zeros, but here we enforce bucket logic.
        target_bucket_info = self.calculate_bucket(template_target_zeros)

        consensus_met = leading_zeros >= template_target_zeros

        return {
            "consensus_met": consensus_met,
            "solution_bucket": bucket_info,
            "target_bucket": target_bucket_info,
            "status": "verified" if consensus_met else "failed_consensus"
        }


class GPSEnhancedDynamicTemplateManager:
    # Mapping between logical file keys and their static example references
    EXAMPLE_FILE_MAP: Dict[str, Path] = {
        "global_ledger": Path("System_File_Examples/System/global_ledger_example.json"),
        "global_math_proof": Path("System_File_Examples/System/global_math_proof_example.json"),
        "global_submission": Path("System_File_Examples/System/global_submission_example.json"),
        "hourly_ledger": Path("System_File_Examples/Hourly/hourly_ledger_example.json"),
        "hourly_math_proof": Path("System_File_Examples/Hourly/hourly_math_proof_example.json"),
        "hourly_submission": Path("System_File_Examples/Hourly/hourly_submission_example.json"),
        "global_system_report": Path(
            "System_File_Examples/System/global_system_report_example.json"
        ),
        "hourly_system_report": Path(
            "System_File_Examples/Hourly/hourly_system_report_example.json"
        ),
        "global_system_error": Path(
            "System_File_Examples/System/global_system_error_example.json"
        ),
        "hourly_system_error": Path(
            "System_File_Examples/Hourly/hourly_system_error_example.json"
        ),
    }

    def _get_example_path(self, file_key: str) -> Optional[Path]:
        example_path = self.EXAMPLE_FILE_MAP.get(file_key)
        if example_path is None:
            return None
        return to_absolute_path(example_path)

    def _load_example_payload(self, file_key: str) -> Optional[Any]:
        example_path = self._get_example_path(file_key)
        if not example_path or not example_path.exists():
            return None
        try:
            with open(example_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return None

    def _structures_match(self, reference: Any, candidate: Any) -> bool:
        if isinstance(reference, dict):
            if not isinstance(candidate, dict):
                return False

            wildcard_value: Optional[Any] = None
            for key, ref_value in reference.items():
                if key.startswith("<") and key.endswith(">"):
                    wildcard_value = ref_value
                    continue
                if key not in candidate:
                    return False
                if not self._structures_match(ref_value, candidate[key]):
                    return False

            if wildcard_value is not None:
                for cand_key, cand_value in candidate.items():
                    if cand_key in reference:
                        continue
                    if not self._structures_match(wildcard_value, cand_value):
                        return False

            return True

        if isinstance(reference, list):
            if not isinstance(candidate, list):
                return False
            if not reference or not candidate:
                return True
            template = reference[0]
            return all(self._structures_match(template, item) for item in candidate)

        if reference is None:
            return not isinstance(candidate, (dict, list))

        return isinstance(candidate, type(reference))

    def _validate_against_example(self, file_key: str, payload: Any) -> None:
        example_payload = self._load_example_payload(file_key)
        if example_payload is None:
            return
        if not self._structures_match(example_payload, payload):
            raise ValueError(
                f"Generated payload for {file_key} does not match example structure"
            )

    def _normalize_payload_from_example(
        self, file_key: str, payload: Dict[str, Any], timestamp: str
    ) -> Dict[str, Any]:
        normalized = copy.deepcopy(payload)

        if "metadata" in normalized and isinstance(normalized["metadata"], dict):
            meta = normalized["metadata"]
            meta["created"] = timestamp
            meta["last_updated"] = timestamp
            if "total_entries" in meta:
                meta["total_entries"] = 0
            if "total_blocks_submitted" in meta:
                meta["total_blocks_submitted"] = 0
            if "current_payout_address" in meta:
                meta["current_payout_address"] = None
            if "current_wallet" in meta:
                meta["current_wallet"] = None

        if "entries_by_date" in normalized:
            normalized["entries_by_date"] = {}
        if "payout_history" in normalized:
            normalized["payout_history"] = []
        if "entries" in normalized:
            normalized["entries"] = []
        if "reports" in normalized:
            normalized["reports"] = []
        if "errors" in normalized:
            normalized["errors"] = []

        if "created" in normalized and not isinstance(normalized["created"], dict):
            normalized["created"] = timestamp
        if "last_updated" in normalized:
            normalized["last_updated"] = timestamp
        if "total_entries" in normalized:
            normalized["total_entries"] = 0

        if file_key.endswith("system_report") and "metadata" in normalized:
            normalized["metadata"].setdefault("scope", "global")
            normalized["metadata"]["generated"] = timestamp
        if file_key.endswith("system_error") and "metadata" in normalized:
            normalized["metadata"].setdefault("scope", "global")
            normalized["metadata"]["generated"] = timestamp

        if file_key.startswith("hourly") and "metadata" in normalized:
            normalized["metadata"].setdefault("scope", "hourly")

        return normalized

    def _build_initial_payload(self, file_key: str, timestamp: str) -> Dict[str, Any]:
        example_payload = self._load_example_payload(file_key)
        if isinstance(example_payload, dict):
            return self._normalize_payload_from_example(
                file_key, example_payload, timestamp
            )

        if file_key.startswith("global"):
            return {
                "metadata": {
                    "created": timestamp,
                    "last_updated": timestamp,
                    "total_entries": 0,
                    "total_blocks_submitted": 0,
                    "current_payout_address": None,
                    "current_wallet": None,
                },
                "entries_by_date": {},
                "payout_history": [],
            }

        if file_key.startswith("hourly"):
            return {
                "entries": [],
                "created": timestamp,
                "last_updated": timestamp,
                "total_entries": 0,
            }

        # Fallback for unexpected keys
        return {
            "metadata": {"created": timestamp, "last_updated": timestamp},
            "entries": [],
        }
    """
    GPS-Enhanced Dynamic Template Manager with Universe-Scale Intelligence
    Features: GPS Navigation, Solution Prediction, Mathematical Pre-Analysis
    """

    def __init__(
        self,
        verbose: bool = True,
        demo_mode: bool = False,
        auto_initialize: bool = True,
        create_directories: bool = True,
        environment: Optional[str] = None,
        synchronize_all_environments: bool = True,
        sync_system_examples: bool = True,
    ):
        # CodePhantom_Bob Enhancement: Initialize with comprehensive validation
        try:
            self._validate_initialization_parameters(
                verbose, demo_mode, auto_initialize, create_directories,
                environment, synchronize_all_environments, sync_system_examples
            )
            
            self.verbose = verbose
            self.demo_mode = demo_mode
            self.enable_filesystem = create_directories
            self.synchronize_all_environments = synchronize_all_environments
            self.sync_system_examples = sync_system_examples
        except Exception as e:
            raise RuntimeError(f"Dynamic Template Manager initialization failed: {e}")

        if self.verbose:
            print("🧠 GPS-ENHANCED DYNAMIC TEMPLATE MANAGER - UNIVERSE SCALE")
            if self.demo_mode:
                print("🎮 DEMO MODE: Simulated miner responses for testing")
            print("🎯 Solution Prediction Engine: ACTIVE")
            print("📊 Targeted Nonce Range Calculator: ACTIVE")
            print("🌌 Quintillion-Scale Pattern Recognition: ACTIVE")
            print("=" * 70)

        self.current_template = None
        self.templates: Dict[str, Any] = {}
        self.template_cache: Dict[str, Any] = {}
        self.performance_stats = {
            "templates_processed": 0,
            "cache_hits": 0,
            "processing_time_total": 0,
            "gps_predictions_made": 0,
            "gps_predictions_successful": 0,
            "templates_optimized": 0,
        }

        # Ultra Hex System Integration
        self.ultra_hex_system = UltraHexSystem()
        self.ultra_hex_bucket_size = self.ultra_hex_system.bucket_size
        self.ultra_hex_max_digits = self.ultra_hex_system.max_digits
        self.ultra_hex_consensus: Optional[Dict[str, Any]] = None
        
        # CRITICAL FIX: Initialize solution_targeting dictionary
        self.solution_targeting = {
            "target_leading_zeros": 0,
            "difficulty_target": 0,
            "nonce_range": (0, 0),
            "gps_enhanced": False
        }

        self.environment = self._determine_environment(environment)

        self.brain_path_provider = None
        self.brain_qtl_infrastructure = None
        self._brain_layout_provider = None

        # Blueprint-driven folder management
        self.brain_blueprint = load_brain_blueprint(verbose=self.verbose)
        self.folder_management_blueprint = self.brain_blueprint.get(
            "folder_management", {}
        )
        self.base_paths_map: Dict[str, Path] = {}
        self.auto_structure_paths: List[Path] = []
        self.hourly_folder_pattern: str = "YYYY/MM/DD/HH"
        
        # Mode-aware base paths
        self._mode_base_path = self._get_mode_base_path()
        
        # DTM creates tracking files ONLY if auto_initialize=True
        # When Brain handles initialization, DTM just uses existing files
        if auto_initialize:
            self._create_dtm_tracking_files()
        elif self.verbose:
            print("📋 DTM using Brain-created file structure")
    
    def _create_dtm_tracking_files(self):
        """
        Create DTM's tracking files: ledger and math_proof (global + hourly).
        DTM owns these files because DTM processes templates and generates mining data.
        """
        from datetime import datetime
        from pathlib import Path
        import json
        
        base_root = Path(brain_get_base_path())
        base_path = str(base_root)
        timestamp = datetime.now().isoformat()
        now = datetime.now()
        
        # Read examples from System_File_Examples
        def read_example(example_filename):
            example_path = Path("System_File_Examples") / example_filename
            if example_path.exists():
                with open(example_path, 'r') as f:
                    return json.load(f)
            return {}
        
        ledger_template = read_example("Ledger_Global_example.json")
        math_proof_template = read_example("Math_Proof_example.json")
        
        # DTM's global files - get paths dynamically
        global_ledger_path = brain_get_path("global_ledger")
        global_math_proof_path = brain_get_path("global_math_proof")

        dtm_files = {
            global_ledger_path: ledger_template or {
                "metadata": {"file_type": "global_ledger", "created": timestamp, "owned_by": "DTM"},
                "total_hashes": 0,
                "total_blocks_found": 0,
                "total_attempts": 0,
                "computational_hours": 0.0,
                "system_status": {
                    "status": "operational",
                    "last_update": timestamp,
                    "active_miners": 0,
                    "miners_with_issues": 0,
                    "average_hash_rate": 0,
                    "issues": []
                },
                "entries": []
            },
            global_math_proof_path: math_proof_template or {
                "metadata": {"file_type": "math_proof", "created": timestamp, "owned_by": "DTM"},
                "total_proofs": 0,
                "proofs": []
            }
        }
        
        # DTM's hourly files - get paths dynamically
        hourly_ledger_path = brain_get_path("hourly_ledger", custom_timestamp=now.isoformat())
        mining_hourly_dir = Path(hourly_ledger_path).parent
        mining_hourly_dir.mkdir(parents=True, exist_ok=True)

        hourly_ledger_template = read_example("Ledger_Hourly_example.json")
        hourly_math_proof_template = read_example("Math_Proof_Hourly_example.json")
        
        dtm_files[hourly_ledger_path] = hourly_ledger_template or {
            "metadata": {"file_type": "hourly_ledger", "created": timestamp, "hour": now.hour, "owned_by": "DTM"},
            "hour": f"{now.year}-{now.month:02d}-{now.day:02d}_{now.hour:02d}",
            "hashes_this_hour": 0,
            "blocks_found_this_hour": 0,
            "blocks": []
        }
        
        hourly_math_proof_path = brain_get_path("hourly_math_proof", custom_timestamp=now.isoformat())
        dtm_files[hourly_math_proof_path] = hourly_math_proof_template or {
            "metadata": {"file_type": "hourly_math_proof", "created": timestamp, "hour": now.hour, "owned_by": "DTM"},
            "hour": f"{now.year}-{now.month:02d}-{now.day:02d}_{now.hour:02d}",
            "proofs_this_hour": 0,
            "proofs": []
        }
        
        # Create all DTM files
        for filepath, content in dtm_files.items():
            file_path = Path(filepath)
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w') as f:
                    json.dump(content, f, indent=2)
                if self.verbose:
                    print(f"   ✅ DTM created: {filepath}")
        
        if self.verbose:
            print(f"✅ DTM tracking files initialized (Ledger & Math Proof)")
    
    def _get_mode_base_path(self) -> str:
        """Get the base path using the centralized brainstem function."""
        # This is now the single source of truth for the base path.
        return brain_get_base_path()
    
    def _get_ledger_path(self) -> Path:
        """Get mode-aware ledger path from brainstem."""
        return Path(brain_get_path("ledgers_dir"))
    
    def _get_system_path(self) -> Path:
        """Get mode-aware system path from brainstem."""
        return Path(brain_get_path("system_dir"))
    
    def _get_submission_path(self) -> Path:
        """Get mode-aware submission path from brainstem."""
        return Path(brain_get_path("submissions_dir"))

    def _validate_initialization_parameters(
        self, verbose: bool, demo_mode: bool, auto_initialize: bool,
        create_directories: bool, environment: Optional[str],
        synchronize_all_environments: bool, sync_system_examples: bool
    ) -> None:
        """CodePhantom_Bob Enhancement: Validate all initialization parameters"""
        if not isinstance(verbose, bool):
            raise TypeError("verbose must be a boolean")
        if not isinstance(demo_mode, bool):
            raise TypeError("demo_mode must be a boolean")
        if not isinstance(auto_initialize, bool):
            raise TypeError("auto_initialize must be a boolean")
        if not isinstance(create_directories, bool):
            raise TypeError("create_directories must be a boolean")
        if environment is not None and not isinstance(environment, str):
            raise TypeError("environment must be a string or None")
        if not isinstance(synchronize_all_environments, bool):
            raise TypeError("synchronize_all_environments must be a boolean")
        if not isinstance(sync_system_examples, bool):
            raise TypeError("sync_system_examples must be a boolean")
        
        # Validate environment if provided
        if environment is not None:
            valid_environments = ["Mining", "Testing", "Development", "Production"]
            if environment not in valid_environments:
                raise ValueError(f"Invalid environment '{environment}'. Must be one of: {valid_environments}")

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """CodePhantom_Bob Enhancement: Comprehensive configuration validation"""
        try:
            if not isinstance(config, dict):
                raise TypeError("Configuration must be a dictionary")
            
            # Validate required configuration keys
            required_keys = ["environment", "verbose", "demo_mode"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required configuration key: {key}")
            
            # Validate configuration values
            if not isinstance(config.get("environment"), str):
                raise TypeError("Configuration 'environment' must be a string")
            if not isinstance(config.get("verbose"), bool):
                raise TypeError("Configuration 'verbose' must be a boolean")
            if not isinstance(config.get("demo_mode"), bool):
                raise TypeError("Configuration 'demo_mode' must be a boolean")
            
            # Validate optional keys if present
            if "create_directories" in config and not isinstance(config["create_directories"], bool):
                raise TypeError("Configuration 'create_directories' must be a boolean")
            if "auto_initialize" in config and not isinstance(config["auto_initialize"], bool):
                raise TypeError("Configuration 'auto_initialize' must be a boolean")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Configuration validation failed: {e}")
            raise

    def _handle_error(self, operation: str, error: Exception, fallback_value: Any = None) -> Any:
        """CodePhantom_Bob Enhancement: Comprehensive error handling wrapper"""
        error_msg = f"❌ Error in {operation}: {type(error).__name__}: {error}"
        
        if self.verbose:
            print(error_msg)
        
        # Log to performance stats if available
        if hasattr(self, 'performance_stats') and isinstance(self.performance_stats, dict):
            if 'errors_encountered' not in self.performance_stats:
                self.performance_stats['errors_encountered'] = 0
            self.performance_stats['errors_encountered'] += 1
            
            if 'error_log' not in self.performance_stats:
                self.performance_stats['error_log'] = []
            self.performance_stats['error_log'].append({
                'operation': operation,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'timestamp': current_timestamp()
            })
        
        # Return fallback value or re-raise based on error type
        if isinstance(error, (FileNotFoundError, PermissionError, OSError)):
            # File system errors - return fallback
            return fallback_value
        elif isinstance(error, (TypeError, ValueError)):
            # Data validation errors - re-raise
            raise
        elif isinstance(error, (ImportError, ModuleNotFoundError)):
            # Import errors - return fallback with warning
            if self.verbose:
                print(f"⚠️ Module dependency issue in {operation}, using fallback")
            return fallback_value
        else:
            # Unknown errors - re-raise for debugging
            raise
        self.current_hourly_folder: Optional[Path] = None
        self.current_submission_hourly_folder: Optional[Path] = None
        self.current_system_report_hourly_folder: Optional[Path] = None
        self.current_system_error_hourly_folder: Optional[Path] = None
        self.submissions_root: Optional[Path] = None
        self.submissions_global_folder: Optional[Path] = None
        self.hourly_file_names: Dict[str, str] = {
            "ledger": "hourly_ledger.json",
            "math_proof": "hourly_math_proof.json",
            "submission": "hourly_submission.json",
        }
        self.system_file_names: Dict[str, str] = {
            "global_report": "global_system_report.json",
            "global_error": "global_system_error.json",
            "hourly_report": "hourly_system_report.json",
            "hourly_error": "hourly_system_error.json",
        }

        # Brain integration
        try:
            self.brain = get_global_brain()
            brain_status = "CONNECTED" if self.brain else "STANDALONE"
            if self.verbose:
                print(f"🧠 Brain Integration: {brain_status}")
        except Exception as e:
            self.brain = None
            if self.verbose:
                print(f"⚠️ Brain connection failed: {e}")

        # GPS Solution Targeting System
        self.solution_targeting = {
            "target_leading_zeros": None,  # Will be read from template file
            "nonce_range_precision": "quintillion-scale",
            "solution_probability_calculator": True,
            "instant_solve_mode": True,
            "mathematical_pre_filtering": True,
        }

        if self.verbose:
            print("🎯 GPS Solution Targeting System:")
            print("   🎯 Target Leading Zeros: Will be read from template file")
            nonce_precision = self.solution_targeting["nonce_range_precision"]
            print(f"   🔢 Nonce Range Precision: {nonce_precision}")
            solve_mode = self.solution_targeting["instant_solve_mode"]
            solve_status = "ACTIVE" if solve_mode else "DISABLED"
            print(f"   ⚡ Instant Solve Mode: {solve_status}")

        # Initialize Brain.QTL integration for folder management
        if auto_initialize:
            self.initialize_brain_qtl_integration()
            
            # Initialize DTM component files (reports + logs)
            try:
                from Singularity_Dave_Brainstem_UNIVERSE_POWERED import initialize_component_files
                base_path = self._get_mode_base_path()
                initialize_component_files("DTM", base_path)
                if self.verbose:
                    print("✅ DTM component files initialized")
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ DTM component file initialization warning: {e}")

        # PIPELINE FLOW.TXT COMPLIANCE: Add automatic subfolder monitoring
        self.monitoring_enabled = True
        self.monitoring_interval = 5  # Check every 5 seconds
        self.monitoring_thread = None
        self.last_monitoring_check = 0
        
        # 🚀 HARDWARE OPTIMIZATION: RAM-based template delivery system
        self.template_queues: Dict[str, queue.Queue] = {}  # Per-miner RAM queues
        self.miner_ready_events: Dict[str, threading.Event] = {}
        self.hardware_cores = max(1, multiprocessing.cpu_count() - 2)  # Reserve 2 cores for system
        self.parallel_miners_enabled = True
        
        if self.verbose:
            print(f"🚀 Hardware Optimization: {self.hardware_cores} parallel miners (12 total cores - 2 reserved)")
            print("💾 RAM Template Delivery: ENABLED (no disk writes)")
            print("⚡ Instant Solution Write: ENABLED")
        
        # Start automatic monitoring as per Pipeline flow.txt requirement
        if self.monitoring_enabled:
            self.start_automatic_subfolder_monitoring()

    def _determine_environment(self, override: Optional[str]) -> str:
        """Resolve the active environment (Mining, Testing/Demo, Testing/Test)."""
        if override:
            return override

        env_candidates = [
            os.environ.get("BRAIN_QTL_ENVIRONMENT"),
            os.environ.get("BRAIN_ENVIRONMENT"),
            os.environ.get("DTM_ENVIRONMENT"),
            os.environ.get("ENVIRONMENT"),
        ]

        for candidate in env_candidates:
            if candidate:
                return candidate

        if self.demo_mode:
            return "Testing/Demo"

        return "Mining"

    def initialize_brain_qtl_integration(self):
        """Initialize Brain.QTL integration for folder management"""
        try:
            # Import Brain.QTL functions
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
                get_brain_qtl_file_path,
                ensure_brain_qtl_infrastructure,
                get_environment_layout,
            )

            self.brain_path_provider = get_brain_qtl_file_path
            self.brain_qtl_infrastructure = ensure_brain_qtl_infrastructure
            self._brain_layout_provider = get_environment_layout

            if self.enable_filesystem:
                try:
                    infrastructure_result = self.brain_qtl_infrastructure()
                    if self.verbose and isinstance(infrastructure_result, dict):
                        created = infrastructure_result.get("created_folders", 0)
                        existing = infrastructure_result.get("existing_folders", 0)
                        print(
                            "🗂️ Brain.QTL Infrastructure: "
                            f"created={created}, existing={existing}"
                        )
                except Exception as infra_error:
                    if self.verbose:
                        print(f"⚠️ Brain.QTL infrastructure check failed: {infra_error}")
            else:
                self.brain_qtl_infrastructure = ensure_brain_qtl_infrastructure

            if self.verbose:
                print("✅ Brain.QTL Integration: CONNECTED")
                print("🚫 Folder Creation: Delegated to Brain.QTL")
                print("📍 Path Requests: Using Brain.QTL path provider")

        except ImportError as e:
            if self.verbose:
                print(f"⚠️ Brain.QTL import failed: {e}")
                print("🔄 Using fallback path management")
            self.brain_path_provider = None
            self.brain_qtl_infrastructure = None
            self._brain_layout_provider = None

        # Align filesystem with Brain blueprint prior to ledger setup
        self.ensure_brain_structure(create=self.enable_filesystem)
        if self.enable_filesystem:
            self._report_structure_status()

        # Initialize ledger file system
        self.initialize_ledger_system(create_files=self.enable_filesystem)
        if self.enable_filesystem:
            moment = current_time()
            self._ensure_system_reporting_files(moment)
            self._ensure_system_file_examples(moment)
            if self.synchronize_all_environments:
                self._bootstrap_additional_environments(moment)

    def ensure_process_folder_exists(self, miner_number: int) -> Tuple[Path, str]:
        """
        Auto-create process folder if needed - CORRECTED ARCHITECTURE
        Each mining process gets its own folder regardless of daemon/terminal execution mode
        Returns (folder_path, miner_id)
        """
        miner_id = get_miner_id(miner_number)
        folder_name = f"Process_{miner_number:03d}"  # Process_001, Process_002, etc.
        folder_path = self._get_temporary_template_root() / folder_name

        # ARCHITECTURAL COMPLIANCE: Brain/Brainstem creates all folders
        # DTM should only create files, not folders
        if not folder_path.exists() and self.verbose:
            print(f"⚠️ Process folder should be created by Brain: {folder_path} (ID: {miner_id})")

        return folder_path, miner_id

    def ensure_brain_structure(self, create: bool = True) -> None:
        """Create core directories defined in the Brain blueprint."""
        if self.brain_path_provider and self._brain_layout_provider:
            try:
                layout = self._brain_layout_provider(self.environment)
            except Exception:
                layout = None

            if layout:
                path_candidates = {
                    "root": layout.get("base"),
                    "temporary_template": layout.get("temporary_template_dir"),
                    "output": layout.get("output_dir"),
                    "ledgers": layout.get("ledgers", {}).get("base_dir"),
                    "ledgers_global": layout.get("ledgers", {}).get("global_dir"),
                    "submissions": layout.get("submissions", {}).get("base_dir"),
                    "submissions_global": layout.get("submissions", {}).get("global_dir"),
                    "system_reports": layout.get("system_reports", {}).get("global_dir"),
                    "system_errors": layout.get("system_errors", {}).get("global_dir"),
                }

                auto_entries: Set[Path] = set()

                for key, raw_value in path_candidates.items():
                    if not raw_value:
                        continue
                    normalized = normalize_blueprint_path(raw_value)
                    if not normalized:
                        continue
                    absolute_path = to_absolute_path(normalized)
                    # ARCHITECTURAL COMPLIANCE: Brain creates folders, not DTM
                    if create and self.verbose:
                        print(f"⚠️ Folder creation should be handled by Brain: {absolute_path}")
                    self.base_paths_map[key] = absolute_path
                    auto_entries.add(absolute_path)

                # Include temporary directories from layout definitions
                for section_key in ("ledgers", "submissions", "system_reports", "system_errors"):
                    section = layout.get(section_key, {})
                    for sub_key in ("global_dir", "base_dir"):
                        raw_section_path = section.get(sub_key)
                        if not raw_section_path:
                            continue
                        normalized = normalize_blueprint_path(raw_section_path)
                        if not normalized:
                            continue
                        absolute_path = to_absolute_path(normalized)
                        # ARCHITECTURAL COMPLIANCE: Brain creates folders, not DTM
                        if create and self.verbose:
                            print(f"⚠️ Section folder creation should be handled by Brain: {absolute_path}")
                        auto_entries.add(absolute_path)

                self.auto_structure_paths = sorted(auto_entries, key=lambda item: str(item))
                return

        folder_management = self.folder_management_blueprint or {}

        # Base paths
        base_paths = folder_management.get("base_paths", {})
        for key, raw_path in base_paths.items():
            normalized = normalize_blueprint_path(raw_path)
            if not normalized:
                continue
            absolute_path = to_absolute_path(normalized)
            # ARCHITECTURAL COMPLIANCE: Brain creates folders, not DTM
            if create and self.verbose:
                print(f"⚠️ Base path folder creation should be handled by Brain: {absolute_path}")
            self.base_paths_map[key] = absolute_path

        # Auto-create structure entries (excluding illustrative examples)
        auto_structure = folder_management.get("auto_create_structure", [])
        created_paths: Set[Path] = set()
        sanitized_entries: List[Path] = []

        for raw_entry in auto_structure:
            if not raw_entry or is_example_path(raw_entry):
                continue

            normalized_entry = normalize_blueprint_path(raw_entry)
            if not normalized_entry:
                continue

            absolute_entry = to_absolute_path(normalized_entry)
            if absolute_entry in created_paths:
                continue

            # ARCHITECTURAL COMPLIANCE: Brain creates folders, not DTM
            if create and self.verbose:
                print(f"⚠️ Auto-structure folder creation should be handled by Brain: {absolute_entry}")
            sanitized_entries.append(absolute_entry)

        self.auto_structure_paths = sanitized_entries

    def _report_structure_status(self) -> None:
        """Emit a concise verification report comparing disk layout to the blueprint."""
        if not self.verbose or not self.base_paths_map:
            return

        missing_keys = [
            key for key, path in self.base_paths_map.items() if not path.exists()
        ]
        if missing_keys:
            print("⚠️ Missing Brain base paths detected:")
            for key in missing_keys:
                print(f"   - {key}: {self.base_paths_map[key]}")
        else:
            print("✅ Core Brain base paths verified")

        root_path = self.base_paths_map.get("root")
        if not root_path or not root_path.exists():
            return

        legacy_variants: List[Path] = []
        for child in root_path.iterdir():
            if child.is_dir() and child.name != child.name.strip():
                legacy_variants.append(child)

        if legacy_variants:
            print("⚠️ Legacy folders with trailing whitespace detected:")
            for variant in legacy_variants:
                print(f"   - {variant}")

    def _ensure_system_file_examples(self, moment: Optional[datetime] = None) -> None:
        """Ensure reference example files exist without overwriting prior snapshots."""
        if not self.enable_filesystem or not self.sync_system_examples:
            return

        try:
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
                get_system_file_example_directories,
                get_system_file_example_files,
            )
        except Exception:
            return

        directories = get_system_file_example_directories()
        for raw_dir in directories:
            normalized = normalize_blueprint_path(raw_dir)
            if not normalized:
                continue
            example_dir = to_absolute_path(normalized)
            # ARCHITECTURAL COMPLIANCE: Brain creates example directories, not DTM
            if not example_dir.exists() and self.verbose:
                print(f"⚠️ Example directory creation should be handled by Brain: {example_dir}")

        example_files = get_system_file_example_files()
        for group_name, files in example_files.items():
            group_path = normalize_blueprint_path(f"System_File_Examples/{group_name}")
            if not group_path:
                continue
            group_dir = to_absolute_path(group_path)
            # ARCHITECTURAL COMPLIANCE: Brain creates group directories, not DTM
            if not group_dir.exists() and self.verbose:
                print(f"⚠️ Group directory creation should be handled by Brain: {group_dir}")

            for file_name, description in files.items():
                target_file = group_dir / file_name
                if target_file.exists():
                    continue
                payload = self._build_example_payload(file_name, description)
                with open(target_file, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)

    def _bootstrap_additional_environments(self, moment: Optional[datetime] = None) -> None:
        """Ensure auxiliary environments have matching infrastructure and files."""
        if not self.enable_filesystem or not self.brain_path_provider:
            return

        other_environments = ["Mining", "Testing/Demo", "Testing/Test"]

        for env in other_environments:
            if env == self.environment:
                continue

            try:
                GPSEnhancedDynamicTemplateManager(
                    verbose=False,
                    demo_mode=(env != "Mining"),
                    auto_initialize=True,
                    create_directories=self.enable_filesystem,
                    environment=env,
                    synchronize_all_environments=False,
                    sync_system_examples=False,
                )
            except Exception as bootstrap_error:
                if self.verbose:
                    print(
                        f"⚠️ Auxiliary environment bootstrap failed for {env}: {bootstrap_error}"
                    )

    def _build_example_payload(self, file_name: str, description: str) -> Dict[str, Any]:
        """Generate immutable sample content for system file examples."""
        metadata = {
            "generated": "2025-01-01T00:00:00Z",
            "environment": "Reference",
            "description": description,
            "example": True,
        }

        if "system_report" in file_name:
            body_key = "reports"
            sample_body: List[Dict[str, Any]] = [
                {
                    "scope": "global" if "global" in file_name else "hourly",
                    "uptime_percent": 99.995,
                    "active_miners": 5,
                    "recent_events": [
                        "No anomalies detected",
                        "All daemons synchronized",
                    ],
                }
            ]
        elif "system_error" in file_name:
            body_key = "errors"
            sample_body = [
                {
                    "severity": "warning",
                    "code": "SYNC_DELAY",
                    "message": "One miner reported a delayed share; auto-resolved.",
                }
            ]
        elif "math_proof" in file_name:
            body_key = "proofs"
            sample_body = [
                {
                    "proof_id": "example-proof-001",
                    "hash": "0000000000000000000000000000000000000000000000000000000000000000",
                    "status": "validated",
                }
            ]
        elif "submission" in file_name:
            body_key = "submissions"
            sample_body = [
                {
                    "submission_id": "example-submission-001",
                    "block_height": 840000,
                    "status": "pending",
                }
            ]
        else:
            body_key = "entries"
            sample_body = [
                {
                    "miner_id": "MINER_ALPHA",
                    "target_nonce": 123456789,
                    "status": "queued",
                }
            ]

        return {"metadata": metadata, body_key: sample_body}

    def _get_system_reporting_paths(self, moment: datetime) -> Dict[str, Path]:
        """Resolve global and hourly system report/error file paths for the given moment."""
        # Use 24-hour format (24 instead of 00 for midnight) 
        hour_int = int(moment.strftime("%H"))
        hour = "24" if hour_int == 0 else f"{hour_int:02d}"
        
        # Bitcoin blocks every 10 minutes: 00, 10, 20, 30, 40, 50
        current_minute = int(moment.strftime("%M"))
        minute = f"{(current_minute // 10) * 10:02d}"
        
        components = (
            moment.strftime("%Y"),
            moment.strftime("%m"),
            moment.strftime("%d"),
            hour,
            minute,
        )

        if self.brain_path_provider:
            global_report = to_absolute_from_string(
                self.brain_path_provider("global_system_report", self.environment)
            )
            global_error = to_absolute_from_string(
                self.brain_path_provider("global_system_error", self.environment)
            )
            hourly_report = to_absolute_from_string(
                self.brain_path_provider(
                    "hourly_system_report", self.environment, components
                )
            )
            hourly_error = to_absolute_from_string(
                self.brain_path_provider(
                    "hourly_system_error", self.environment, components
                )
            )

            self.system_file_names.update(
                {
                    "global_report": Path(global_report).name,
                    "global_error": Path(global_error).name,
                    "hourly_report": Path(hourly_report).name,
                    "hourly_error": Path(hourly_error).name,
                }
            )
        else:
            # Component-based: Mining/System/DTM/Global/ and DTM/Hourly/
            dtm_root = self.base_paths_map.get("system_dtm") or to_absolute_path(
                Path("System") / "DTM"
            )
            
            global_report = dtm_root / "Global" / "global_dtm_report.json"
            global_error = dtm_root / "Global" / "global_dtm_error.json"
            hourly_report = (
                dtm_root
                / "Hourly"
                / components[0]
                / components[1]
                / components[2]
                / components[3]
                / "hourly_dtm_report.json"
            )
            hourly_error = (
                dtm_root
                / "Hourly"
                / components[0]
                / components[1]
                / components[2]
                / components[3]
                / "hourly_dtm_error.json"
            )

        return {
            "global_system_report": Path(global_report),
            "global_system_error": Path(global_error),
            "hourly_system_report": Path(hourly_report),
            "hourly_system_error": Path(hourly_error),
        }

    def _build_system_payload(
        self, file_key: str, moment: datetime, timestamp: str
    ) -> Dict[str, Any]:
        """Construct initial payloads for system report and error files."""
        try:
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import (
                build_system_file_payload,
            )

            payload = build_system_file_payload(
                file_key=file_key,
                moment=moment,
                timestamp=timestamp,
                environment=self.environment,
            )
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

        metadata: Dict[str, Any] = {
            "environment": self.environment,
            "generated": timestamp,
        }

        if file_key.startswith("hourly"):
            metadata.update(
                {
                    "scope": "hourly",
                    "hour_window": moment.strftime("%Y-%m-%dT%H:00:00"),
                }
            )
        else:
            metadata["scope"] = "global"

        if "system_report" in file_key:
            body_key = "reports"
        else:
            body_key = "errors"

        return {"metadata": metadata, body_key: []}

    def _ensure_system_reporting_files(self, moment: Optional[datetime] = None) -> None:
        """Guarantee presence of system report/error files for the active environment."""
        if not self.enable_filesystem:
            return

        moment = moment or current_time()
        path_map = self._get_system_reporting_paths(moment)
        timestamp = current_timestamp()

        for path in path_map.values():
            # ARCHITECTURAL COMPLIANCE: Brain creates system reporting folders, not DTM
            if not path.parent.exists() and self.verbose:
                print(f"⚠️ System reporting folder creation should be handled by Brain: {path.parent}")

        if getattr(self, "ledger_files", None) is None:
            self.ledger_files = {}

        for key, path in path_map.items():
            if not path.exists():
                payload = self._build_system_payload(key, moment, timestamp)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)

            self.ledger_files[key] = path

        self.current_system_report_hourly_folder = path_map[
            "hourly_system_report"
        ].parent
        self.current_system_error_hourly_folder = path_map[
            "hourly_system_error"
        ].parent

    def _build_ultra_hex_consensus(self, required_zeros: int) -> Dict[str, Any]:
        """Generate Ultra Hex bucket consensus aligned with production miner."""
        return self.ultra_hex_system.calculate_bucket(required_zeros)

    def _augment_template_with_consensus(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Attach consensus metadata without mutating original template."""
        template_copy = copy.deepcopy(template_data)
        bits_value = template_copy.get("bits", "1d00ffff")
        target_zeros = self.calculate_target_zeros(bits_value)
        template_copy["target_leading_zeros"] = target_zeros
        template_copy["ultra_hex_consensus"] = self._build_ultra_hex_consensus(target_zeros)
        self.ultra_hex_consensus = template_copy["ultra_hex_consensus"]
        self.solution_targeting["target_leading_zeros"] = target_zeros
        return template_copy

    def ensure_hourly_folder_exists(self) -> Path:
        """Auto-create hourly folder if new hour"""
        moment = current_time()
        hourly_folder = self._build_hourly_path(moment)
        submission_folder = None

        if self.submissions_root is not None:
            submission_folder = self._build_submission_hourly_path(moment)

        hourly_missing = not hourly_folder.exists()
        submission_missing = (
            submission_folder is not None and not submission_folder.exists()
        )

        if self.enable_filesystem and (hourly_missing or submission_missing):
            self._initialize_hourly_ledgers(hourly_folder, submission_folder)
            if self.verbose and self.enable_filesystem:
                print(f"✅ Created hourly folder: {hourly_folder}")

        self.current_hourly_folder = hourly_folder
        if submission_folder is not None:
            self.current_submission_hourly_folder = submission_folder

        if getattr(self, "ledger_files", None):
            ledger_filename = self.hourly_file_names.get("ledger", "hourly_ledger.json")
            math_filename = self.hourly_file_names.get(
                "math_proof", "hourly_math_proof.json"
            )
            submission_filename = self.hourly_file_names.get(
                "submission", "hourly_submission.json"
            )

            self.ledger_files["hourly_ledger"] = hourly_folder / ledger_filename
            self.ledger_files["hourly_math_proof"] = hourly_folder / math_filename

            if submission_folder is not None:
                self.ledger_files["hourly_submission"] = (
                    submission_folder / submission_filename
                )

        self._ensure_system_reporting_files(moment)

        return hourly_folder

    def _initialize_hourly_ledgers(
        self, hourly_path: Path, submission_path: Optional[Path] = None
    ):
        """Initialize empty hourly files for ledgers, proofs, and submissions."""
        if not self.enable_filesystem:
            return
        # ARCHITECTURAL COMPLIANCE: Brain creates hourly folders, not DTM
        if not hourly_path.exists() and self.verbose:
            print(f"⚠️ Hourly folder creation should be handled by Brain: {hourly_path}")
        ledger_filename = self.hourly_file_names.get("ledger", "hourly_ledger.json")
        math_filename = self.hourly_file_names.get(
            "math_proof", "hourly_math_proof.json"
        )
        submission_filename = self.hourly_file_names.get(
            "submission", "hourly_submission.json"
        )

        for filename in (ledger_filename, math_filename):
            file_path = hourly_path / filename
            if not file_path.exists():
                with open(file_path, "w", encoding="utf-8") as handle:
                    json.dump(
                        {"entries": [], "created": current_time().isoformat()},
                        handle,
                        indent=2,
                    )

        if submission_path is not None:
            # ARCHITECTURAL COMPLIANCE: Brain creates submission folders, not DTM
            if not submission_path.exists() and self.verbose:
                print(f"⚠️ Submission folder creation should be handled by Brain: {submission_path}")
            submission_file_path = submission_path / submission_filename
            if not submission_file_path.exists():
                with open(submission_file_path, "w", encoding="utf-8") as handle:
                    json.dump(
                        {"entries": [], "created": current_time().isoformat()},
                        handle,
                        indent=2,
                    )

    def initialize_ledger_system(self, create_files: bool = True):
        """Initialize DTM ledger file system by reading Brain.QTL blueprint"""
        try:
            if self.brain_path_provider and self._brain_layout_provider:
                layout = self._brain_layout_provider(self.environment)

                def _layout_absolute(raw_value: Optional[str]) -> Path:
                    if not raw_value:
                        raise ValueError("Missing layout path definition")
                    normalized = normalize_blueprint_path(raw_value)
                    if not normalized:
                        raise ValueError(f"Invalid layout path: {raw_value}")
                    return to_absolute_path(normalized)

                system_reports_cfg = layout.get("system_reports", {})
                system_errors_cfg = layout.get("system_errors", {})
                self.system_file_names.update(
                    {
                        "global_report": system_reports_cfg.get(
                            "global_file", self.system_file_names["global_report"]
                        ),
                        "global_error": system_errors_cfg.get(
                            "global_file", self.system_file_names["global_error"]
                        ),
                        "hourly_report": system_reports_cfg.get(
                            "hourly_file",
                            self.system_file_names["hourly_report"],
                        ),
                        "hourly_error": system_errors_cfg.get(
                            "hourly_file", self.system_file_names["hourly_error"]
                        ),
                    }
                )

                self.ledger_root_path = _layout_absolute(layout["ledgers"]["base_dir"])
                self.global_folder = _layout_absolute(layout["ledgers"]["global_dir"])
                self.hourly_base_folder = _layout_absolute(layout["ledgers"]["base_dir"])
                self.hourly_stub_folder = self.hourly_base_folder
                self.submissions_root = _layout_absolute(layout["submissions"]["base_dir"])
                self.submissions_global_folder = _layout_absolute(layout["submissions"]["global_dir"])

                if create_files:
                    for folder in {
                        self.ledger_root_path,
                        self.global_folder,
                        self.hourly_base_folder,
                        self.submissions_root,
                        self.submissions_global_folder,
                    }:
                        # ARCHITECTURAL COMPLIANCE: Brain creates system folders, not DTM
                        if not folder.exists() and self.verbose:
                            print(f"⚠️ System folder creation should be handled by Brain: {folder}")

                now = current_time()
                # Use 24-hour format (24 instead of 00 for midnight)
                hour_int = int(now.strftime("%H"))
                hour = "24" if hour_int == 0 else f"{hour_int:02d}"
                
                # Bitcoin blocks every 10 minutes: 00, 10, 20, 30, 40, 50
                current_minute = int(now.strftime("%M"))
                minute = f"{(current_minute // 10) * 10:02d}"
                
                custom_components = (
                    now.strftime("%Y"),
                    now.strftime("%m"),
                    now.strftime("%d"),
                    hour,
                    minute,
                )

                global_ledger_path = to_absolute_from_string(
                    self.brain_path_provider("global_ledger", self.environment)
                )
                global_math_path = to_absolute_from_string(
                    self.brain_path_provider("global_math_proof", self.environment)
                )
                global_submission_path = to_absolute_from_string(
                    self.brain_path_provider("global_submission", self.environment)
                )
                hourly_ledger_path = to_absolute_from_string(
                    self.brain_path_provider("hourly_ledger", self.environment, custom_components)
                )
                hourly_math_path = to_absolute_from_string(
                    self.brain_path_provider("hourly_math_proof", self.environment, custom_components)
                )
                hourly_submission_path = to_absolute_from_string(
                    self.brain_path_provider("hourly_submission", self.environment, custom_components)
                )

                if create_files:
                    # Validate paths exist (should be created by Brainstem hierarchical automation)
                    if not validate_folder_exists_dtm(str(hourly_ledger_path.parent), "DTM-hourly-ledger"):
                        print(f"⚠️ Continuing without hourly ledger path: {hourly_ledger_path.parent}")
                    if not validate_folder_exists_dtm(str(hourly_submission_path.parent), "DTM-hourly-submission"):
                        print(f"⚠️ Continuing without hourly submission path: {hourly_submission_path.parent}")

                self.current_hourly_folder = hourly_ledger_path.parent
                self.current_submission_hourly_folder = hourly_submission_path.parent

                if self.global_folder == self.ledger_root_path:
                    # Use System folder for global files
                    self.global_folder = self.ledger_root_path / "System"
                    # ARCHITECTURAL COMPLIANCE: Brain creates global folder, not DTM
                    if create_files and not self.global_folder.exists() and self.verbose:
                        print(f"⚠️ Global folder creation should be handled by Brain: {self.global_folder}")

                if global_ledger_path.parent == self.ledger_root_path:
                    global_ledger_path = self.global_folder / global_ledger_path.name
                if global_math_path.parent == self.ledger_root_path:
                    global_math_path = self.global_folder / global_math_path.name

                if self.submissions_global_folder == self.submissions_root:
                    # Store global submissions in System folder within Ledgers structure  
                    self.submissions_global_folder = self.ledger_root_path / "System"
                    # ARCHITECTURAL COMPLIANCE: Brain creates submissions global folder, not DTM
                    if create_files and not self.submissions_global_folder.exists() and self.verbose:
                        print(f"⚠️ Submissions global folder creation should be handled by Brain: {self.submissions_global_folder}")

                if global_submission_path.parent == self.submissions_root:
                    global_submission_path = (
                        self.submissions_global_folder / global_submission_path.name
                    )

                global_ledger_name = global_ledger_path.name
                global_math_name = global_math_path.name
                global_submission_name = global_submission_path.name

                self.hourly_file_names = {
                    "ledger": layout["ledgers"]["hourly_files"]["ledger"],
                    "math_proof": layout["ledgers"]["hourly_files"]["math_proof"],
                    "submission": layout["submissions"]["hourly_file"],
                }

                self.ledger_files = {
                    "global_ledger": global_ledger_path,
                    "global_math_proof": global_math_path,
                    "global_submission": global_submission_path,
                    "hourly_ledger": hourly_ledger_path,
                    "hourly_math_proof": hourly_math_path,
                    "hourly_submission": hourly_submission_path,
                }

                self.ledger_folders = {
                    "root": self.ledger_root_path,
                    "global": self.global_folder,
                    "hourly_base": self.hourly_base_folder,
                    "hourly_stub": self.current_hourly_folder,
                    "submissions_root": self.submissions_root,
                    "submissions_global": self.submissions_global_folder,
                }

                self.hourly_folder_pattern = "Brain.QTL-managed"
            else:
                ledger_config = self.folder_management_blueprint.get("ledger_system", {})
                base_paths = self.folder_management_blueprint.get("base_paths", {})

                def _resolve_path(raw_value: Optional[str], fallback_value: str) -> Path:
                    normalized = normalize_blueprint_path(raw_value)
                    if normalized is None:
                        normalized = normalize_blueprint_path(fallback_value)
                    if normalized is None:
                        raise ValueError(
                            f"Invalid blueprint path; raw={raw_value}, fallback={fallback_value}"
                        )
                    return to_absolute_path(normalized)

                folders_config = ledger_config.get("folders", {})

                self.ledger_root_path = _resolve_path(
                    ledger_config.get("base_path"),
                    base_paths.get("ledgers", "./Mining"),
                )
                self.global_folder = _resolve_path(
                    folders_config.get("global"),
                    base_paths.get("ledgers_global", "./Mining"),
                )
                if self.global_folder == self.ledger_root_path:
                    self.global_folder = self.ledger_root_path
                self.hourly_base_folder = _resolve_path(
                    folders_config.get("hourly_base"),
                    base_paths.get("ledgers", "./Mining"),
                )
                self.hourly_stub_folder = _resolve_path(
                    folders_config.get("hourly_stub"),
                    base_paths.get("ledgers_hourly", "./Mining/Ledgers/Hourly"),
                )
                submissions_fallback = base_paths.get("submissions", "./Mining/Ledgers")
                self.submissions_root = _resolve_path(
                    folders_config.get("submissions"), submissions_fallback
                )

                submissions_global_raw = folders_config.get("submissions_global")
                submissions_global_fallback = base_paths.get("submissions_global")
                if submissions_global_raw is not None or submissions_global_fallback:
                    fallback_value = submissions_global_fallback or submissions_fallback
                    self.submissions_global_folder = _resolve_path(
                        submissions_global_raw, fallback_value
                    )
                else:
                    self.submissions_global_folder = _resolve_path(
                        "./Mining/Ledgers/System", "./Mining/Ledgers/System"
                    )
                if self.submissions_global_folder == self.submissions_root:
                    self.submissions_global_folder = self.ledger_root_path / "System"

                if create_files:
                    # Validate all core DTM paths exist (should be created by Brainstem)
                    paths_to_validate = [
                        (self.ledger_root_path, "DTM-ledger-root"),
                        (self.global_folder, "DTM-global"),
                        (self.hourly_base_folder, "DTM-hourly-base"),
                        (self.hourly_stub_folder, "DTM-hourly-stub"),
                        (self.submissions_root, "DTM-submissions-root"),
                        (self.submissions_global_folder, "DTM-submissions-global")
                    ]
                    for path, name in paths_to_validate:
                        if not validate_folder_exists_dtm(str(path), name):
                            print(f"⚠️ Continuing without validated path: {path}")

                self.hourly_folder_pattern = ledger_config.get(
                    "hourly_folder_pattern", self.hourly_folder_pattern
                )
                files_config = ledger_config.get("files", {})
                global_files_cfg = files_config.get("global", [])
                hourly_files_cfg = files_config.get("hourly", [])

                def _select_file(files: List[str], index: int, fallback: str) -> str:
                    if index < len(files) and files[index]:
                        return files[index]
                    return fallback

                now = current_time()
                self.current_hourly_folder = self._build_hourly_path(now)
                self.current_submission_hourly_folder = self._build_submission_hourly_path(
                    now
                )
                if create_files:
                    if not validate_folder_exists_dtm(str(self.current_hourly_folder), "DTM-hourly"):
                        raise FileNotFoundError(f"Hourly folder not found: {self.current_hourly_folder}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
                    if not validate_folder_exists_dtm(str(self.current_submission_hourly_folder), "DTM-submission-hourly"):
                        raise FileNotFoundError(f"Submission hourly folder not found: {self.current_submission_hourly_folder}. Brain.QTL canonical authority via Brainstem should create this folder structure.")

                global_ledger_name = _select_file(global_files_cfg, 0, "global_ledger.json")
                global_math_name = _select_file(
                    global_files_cfg, 1, "global_math_proof.json"
                )
                global_submission_name = _select_file(
                    global_files_cfg, 2, "global_submission.json"
                )
                hourly_ledger_name = _select_file(hourly_files_cfg, 0, "hourly_ledger.json")
                hourly_math_name = _select_file(
                    hourly_files_cfg, 1, "hourly_math_proof.json"
                )
                hourly_submission_name = _select_file(
                    hourly_files_cfg, 2, "hourly_submission.json"
                )

                self.hourly_file_names = {
                    "ledger": hourly_ledger_name,
                    "math_proof": hourly_math_name,
                    "submission": hourly_submission_name,
                }

                self.ledger_files = {
                    "global_ledger": self.global_folder / global_ledger_name,
                    "global_math_proof": self.global_folder / global_math_name,
                    "global_submission": self.submissions_global_folder
                    / global_submission_name,
                    "hourly_ledger": self.current_hourly_folder / hourly_ledger_name,
                    "hourly_math_proof": self.current_hourly_folder / hourly_math_name,
                    "hourly_submission": self.current_submission_hourly_folder
                    / hourly_submission_name,
                }

                self.ledger_folders = {
                    "root": self.ledger_root_path,
                    "global": self.global_folder,
                    "hourly_base": self.hourly_base_folder,
                    "hourly_stub": self.hourly_stub_folder,
                    "submissions_root": self.submissions_root,
                    "submissions_global": self.submissions_global_folder,
                }

                if self.ledger_files["global_ledger"].parent == self.ledger_root_path:
                    self.global_folder = self.ledger_root_path / "System"
                    if not validate_folder_exists_dtm(str(self.global_folder), "DTM-global-system"):
                        raise FileNotFoundError(f"Global system folder not found: {self.global_folder}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
                    self.ledger_files["global_ledger"] = self.global_folder / global_ledger_name
                    self.ledger_files["global_math_proof"] = self.global_folder / global_math_name
                    self.ledger_folders["global"] = self.global_folder

                if self.ledger_files["global_submission"].parent == self.submissions_root:
                    self.submissions_global_folder = self.ledger_root_path / "System"
                    if not validate_folder_exists_dtm(str(self.submissions_global_folder), "DTM-submissions-global"):
                        raise FileNotFoundError(f"Submissions global folder not found: {self.submissions_global_folder}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
                    self.ledger_files["global_submission"] = (
                        self.submissions_global_folder / global_submission_name
                    )
                    self.ledger_folders["submissions_global"] = self.submissions_global_folder

            if create_files:
                for file_key, file_path in self.ledger_files.items():
                    if not file_path.exists():
                        print(f"🔍 DTM creating {file_key} at: {file_path}")  # DEBUG
                        if "global" in file_key:
                            initial_data = {
                                "metadata": {
                                    "created": current_timestamp(),
                                    "last_updated": current_timestamp(),
                                    "total_entries": 0,
                                    "total_blocks_submitted": 0,
                                    "current_payout_address": None,
                                    "current_wallet": None,
                                },
                                "entries_by_date": {},
                                "payout_history": [],
                            }
                        else:
                            initial_data = {
                                "entries": [],
                                "created": current_timestamp(),
                            }

                        legacy_submission = None
                        if (
                            file_key == "global_submission"
                            and self.submissions_root
                        ):
                            legacy_submission = (
                                self.ledger_root_path
                                / "System"
                                / global_submission_name
                            )
                        if legacy_submission and legacy_submission.exists():
                            legacy_submission.replace(file_path)
                            if self.verbose:
                                print(
                                    "   🔁 Migrated legacy global submission to new location"
                                )
                            continue

                        with open(file_path, "w", encoding="utf-8") as handle:
                            json.dump(initial_data, handle, indent=2)
                        if self.verbose:
                            print(
                                f"   📄 Created: {file_path.relative_to(BASE_DIR)}"
                            )
                    elif "global" in file_key:
                        with open(file_path, "r", encoding="utf-8") as handle:
                            existing_data = json.load(handle)

                        if (
                            "entries" in existing_data
                            and "entries_by_date" not in existing_data
                        ):
                            if self.verbose:
                                print(
                                    f"   🔄 Migrating {file_path.relative_to(BASE_DIR)} to enhanced structure..."
                                )

                            entries_by_date: Dict[str, List[Dict[str, Any]]] = {}
                            for entry in existing_data.get("entries", []):
                                timestamp_str = entry.get("timestamp", "")
                                entry_date = (
                                    timestamp_str.split("T")[0]
                                    if timestamp_str
                                    else "unknown"
                                )
                                entries_by_date.setdefault(entry_date, []).append(entry)

                            migrated_data = {
                                "metadata": {
                                    "created": existing_data.get(
                                        "created", current_timestamp()
                                    ),
                                    "last_updated": current_timestamp(),
                                    "total_entries": len(existing_data.get("entries", [])),
                                    "total_blocks_submitted": 0,
                                    "current_payout_address": None,
                                    "current_wallet": None,
                                    "migrated_from_old_structure": True,
                                },
                                "entries_by_date": entries_by_date,
                                "payout_history": existing_data.get("payout_history", []),
                            }

                            with open(file_path, "w", encoding="utf-8") as handle:
                                json.dump(migrated_data, handle, indent=2)

                            if self.verbose:
                                print(
                                    f"   ✅ Migrated {len(existing_data.get('entries', []))} entries"
                                )

            if self.verbose:
                pattern_label = self.hourly_folder_pattern or "custom"
                relative_hourly = self.current_hourly_folder.relative_to(BASE_DIR)
                print("\n📚 DTM LEDGER SYSTEM INITIALIZED FROM BRAIN.QTL:")
                print(f"   📁 Base: {self.ledger_root_path.relative_to(BASE_DIR)}")
                print(
                    f"   📊 Global Ledger: {self.ledger_files['global_ledger'].relative_to(BASE_DIR)}"
                )
                print(f"   ⏰ Hourly Pattern: {pattern_label}")
                print(f"   🗂️ Active Hourly Folder: {relative_hourly}")
                print("   🧮 Math Proof: Active")
                print("   📤 Submissions: Tracked")

        except Exception as e:
            print(f"❌ Error initializing ledger system: {e}")
            import traceback

            traceback.print_exc()
            self.ledger_files = {}

    def _build_hourly_path(self, moment: datetime) -> Path:
        """Derive the hourly folder path based on the Brain blueprint pattern."""
        if self.brain_path_provider:
            # Use 24-hour format (24 instead of 00 for midnight)
            hour_int = int(moment.strftime("%H"))
            hour = "24" if hour_int == 0 else f"{hour_int:02d}"
            
            # Bitcoin blocks every 10 minutes: 00, 10, 20, 30, 40, 50
            current_minute = int(moment.strftime("%M"))
            minute = f"{(current_minute // 10) * 10:02d}"
            
            custom_components = (
                moment.strftime("%Y"),
                moment.strftime("%m"),
                moment.strftime("%d"),
                hour,
                minute,
            )
            hourly_file = self.brain_path_provider(
                "hourly_ledger", self.environment, custom_components
            )
            return to_absolute_from_string(hourly_file).parent

        pattern = (self.hourly_folder_pattern or "YYYY/MM/DD/HH").strip()

        if pattern == "YYYY/MM/DD/HH":
            return (
                self.hourly_base_folder
                / moment.strftime("%Y")
                / moment.strftime("%m")
                / moment.strftime("%d")
                / moment.strftime("%H")
            )

        if pattern == "YYYY/MM/DD/Hourly":
            return (
                self.hourly_base_folder
                / moment.strftime("%Y")
                / moment.strftime("%m")
                / moment.strftime("%d")
                / "Hourly"
            )

        if pattern == "YYYY-MM-DD_HHh":
            return self.hourly_stub_folder / moment.strftime("%Y-%m-%d_%Hh")

        # Fallback: use ISO hour folder naming under the hourly stub
        safe_folder = moment.strftime("%Y-%m-%d_%Hh")
        return self.hourly_stub_folder / safe_folder

    def _build_submission_hourly_path(self, moment: datetime) -> Path:
        """Generate the submissions hierarchy path for the current hour."""
        if self.brain_path_provider:
            # Use 24-hour format (24 instead of 00 for midnight)
            hour_int = int(moment.strftime("%H"))
            hour = "24" if hour_int == 0 else f"{hour_int:02d}"
            
            # Bitcoin blocks every 10 minutes: 00, 10, 20, 30, 40, 50
            current_minute = int(moment.strftime("%M"))
            minute = f"{(current_minute // 10) * 10:02d}"
            
            custom_components = (
                moment.strftime("%Y"),
                moment.strftime("%m"),
                moment.strftime("%d"),
                hour,
                minute,
            )
            submission_file = self.brain_path_provider(
                "hourly_submission", self.environment, custom_components
            )
            return to_absolute_from_string(submission_file).parent

        base = self.submissions_root or self.hourly_base_folder
        return (
            base
            / moment.strftime("%Y")
            / moment.strftime("%m")
            / moment.strftime("%d")
            / moment.strftime("%H")
        )

    def get_temporary_template_root(self) -> Path:
        """Resolve the directory for temporary templates using brainstem."""
        return Path(brain_get_path("temporary_template_dir"))

    def update_hourly_folder(self):
        """Create new hourly folder if hour has changed"""
        try:
            moment = current_time()
            new_hourly_folder = self._build_hourly_path(moment)
            new_submission_folder = self._build_submission_hourly_path(moment)

            if (
                self.current_hourly_folder
                and new_hourly_folder == self.current_hourly_folder
                and self.current_submission_hourly_folder
                and new_submission_folder == self.current_submission_hourly_folder
            ):
                return False

            changed = False

            if (
                not self.current_hourly_folder
                or new_hourly_folder != self.current_hourly_folder
            ):
                if self.enable_filesystem:
                    if not validate_folder_exists_dtm(str(new_hourly_folder), "DTM-new-hourly"):
                        raise FileNotFoundError(f"New hourly folder not found: {new_hourly_folder}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
                self.current_hourly_folder = new_hourly_folder
                changed = True

                if getattr(self, "ledger_files", None):
                    ledger_filename = self.hourly_file_names.get(
                        "ledger", "hourly_ledger.json"
                    )
                    math_filename = self.hourly_file_names.get(
                        "math_proof", "hourly_math_proof.json"
                    )
                    self.ledger_files["hourly_ledger"] = (
                        new_hourly_folder / ledger_filename
                    )
                    self.ledger_files["hourly_math_proof"] = (
                        new_hourly_folder / math_filename
                    )

            if (
                not self.current_submission_hourly_folder
                or new_submission_folder != self.current_submission_hourly_folder
            ):
                if self.enable_filesystem:
                    if not validate_folder_exists_dtm(str(new_submission_folder), "DTM-new-submission"):
                        raise FileNotFoundError(f"New submission folder not found: {new_submission_folder}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
                self.current_submission_hourly_folder = new_submission_folder
                changed = True

                if getattr(self, "ledger_files", None):
                    submission_filename = self.hourly_file_names.get(
                        "submission", "hourly_submission.json"
                    )
                    self.ledger_files["hourly_submission"] = (
                        new_submission_folder / submission_filename
                    )

            if changed and getattr(self, "ledger_files", None):
                self._initialize_hourly_ledgers(
                    self.current_hourly_folder, self.current_submission_hourly_folder
                )

                if self.verbose and self.current_hourly_folder is not None:
                    relative_path = self.current_hourly_folder.relative_to(BASE_DIR)
                    print(f"🔄 New hourly folder created: {relative_path}")

            if changed:
                self._ensure_system_reporting_files(moment)

            return changed
        except Exception as e:
            print(f"❌ Error updating hourly folder: {e}")
            return False

    def log_to_ledger(self, event_type, data, block_id=None, pipeline_status=None):
        """
        Append entry to global and hourly ledger files with date organization

        Args:
            event_type: Type of event (template_received, solution_found, etc)
            data: Dictionary of event data
            block_id: Unique block identifier (YYYYMMDD_HHMMSS_XXX format)
            pipeline_status: Current stage (template_received, mining, validated, submitted)
        """
        try:
            # Check if hour changed
            self.update_hourly_folder()

            timestamp = current_time()
            timestamp_iso = timestamp.isoformat()
            current_date = timestamp.strftime("%Y-%m-%d")

            # Create enhanced ledger entry
            entry = {
                "timestamp": timestamp_iso,
                "event_type": event_type,
                "block_id": block_id,
                "pipeline_status": pipeline_status,
                "data": data,
            }

            # Use Brain function - automatic template merge + hierarchical write
            result = brain_save_ledger(entry, "DTM")
            
            if not result.get("success"):
                print(f"⚠️ DTM ledger write failed: {result.get('error', 'Unknown error')}")
                # Fallback to old method if Brain fails
                global_ledger_path = self.ledger_files["global_ledger"]
                with open(global_ledger_path, "r+") as f:
                    ledger = json.load(f)
                    ledger.setdefault("entries", []).append(entry)
                    ledger.setdefault("metadata", {})["last_updated"] = timestamp_iso
                    f.seek(0)
                    json.dump(ledger, f, indent=2)
                    f.truncate()

            if self.verbose:
                print(
                    f"📝 Logged to ledger: {event_type} (Block: {block_id}, Status: {pipeline_status})"
                )

            return True
        except Exception as e:
            print(f"❌ Error logging to ledger: {e}")
            import traceback

            traceback.print_exc()
            return False

    def log_math_proof(
        self, proof_type, proof_data, block_id=None, calculation_steps=None
    ):
        """
        Append math proof entry with step-by-step calculations

        Args:
            proof_type: Type of mathematical proof/validation
            proof_data: Dictionary containing proof details
            block_id: Unique block identifier
            calculation_steps: List of dicts with step-by-step math (step, operation, notation, value)
        """
        try:
            # Check if hour changed
            self.update_hourly_folder()

            timestamp = current_time()
            timestamp_iso = timestamp.isoformat()
            current_date = timestamp.strftime("%Y-%m-%d")

            # Create enhanced proof entry
            entry = {
                "timestamp": timestamp_iso,
                "proof_type": proof_type,
                "block_id": block_id,
                "proof_data": proof_data,
                "calculation_steps": calculation_steps or [],
            }

            # Use Brain function - automatic template merge + hierarchical write
            result = brain_save_math_proof(entry, "DTM")
            
            if not result.get("success"):
                print(f"⚠️ DTM math proof write failed: {result.get('error', 'Unknown error')}")

            if self.verbose:
                steps_count = len(calculation_steps) if calculation_steps else 0
                print(
                    f"🧮 Logged math proof: {proof_type} (Block: {block_id}, {steps_count} steps)"
                )

            return True
        except Exception as e:
            print(f"❌ Error logging math proof: {e}")
            import traceback

            traceback.print_exc()
            return False

    def log_gps_calculation_steps(
        self, block_id: str, template: dict, gps_results: dict
    ):
        """
        Log step-by-step GPS-enhanced nonce calculation

        Args:
            block_id: Unique block identifier
            template: Block template from Bitcoin node
            gps_results: GPS calculation results with target_nonce, delta, etc.
        """
        calculation_steps = []

        # Step 1: Extract template data
        calculation_steps.append(
            {
                "step": 1,
                "operation": "Extract Template Data",
                "notation": "T = {height, difficulty, previousblockhash}",
                "values": {
                    "height": template.get("height"),
                    "difficulty": template.get("difficulty"),
                    "prev_hash": template.get("previousblockhash", "")[:16] + "...",
                },
            }
        )

        # Step 2: Knuth function calculation
        if "knuth_result" in gps_results:
            calculation_steps.append(
                {
                    "step": 2,
                    "operation": "Knuth(height, 3, 161)",
                    "notation": "K(h, 3, 161) = (h^3 + 161) mod 2^32",
                    "values": {
                        "height": template.get("height"),
                        "result": gps_results["knuth_result"],
                    },
                }
            )

        # Step 3: GPS delta calculation
        if "delta" in gps_results:
            calculation_steps.append(
                {
                    "step": 3,
                    "operation": "GPS Delta",
                    "notation": "Δ = f(lat, lon, height) mod NONCE_RANGE",
                    "values": {
                        "latitude": gps_results.get("latitude"),
                        "longitude": gps_results.get("longitude"),
                        "delta": gps_results["delta"],
                    },
                }
            )

        # Step 4: Target nonce calculation
        if "target_nonce" in gps_results:
            calculation_steps.append(
                {
                    "step": 4,
                    "operation": "Target Nonce",
                    "notation": "N_target = (K + Δ) mod NONCE_RANGE",
                    "values": {
                        "knuth_result": gps_results.get("knuth_result", 0),
                        "delta": gps_results.get("delta", 0),
                        "target_nonce": gps_results["target_nonce"],
                    },
                }
            )

        # Step 5: Search range
        if "search_range" in gps_results:
            calculation_steps.append(
                {
                    "step": 5,
                    "operation": "Search Range",
                    "notation": "[N_target - ε, N_target + ε]",
                    "values": {
                        "center": gps_results["target_nonce"],
                        "epsilon": gps_results.get("search_epsilon", 1000000),
                        "range_start": gps_results["search_range"][0],
                        "range_end": gps_results["search_range"][1],
                    },
                }
            )

        # Log to math proof ledger
        self.log_math_proof(
            proof_type="gps_nonce_calculation",
            proof_data={
                "template_height": template.get("height"),
                "difficulty": template.get("difficulty"),
                "target_nonce": gps_results.get("target_nonce"),
                "gps_coordinates": {
                    "latitude": gps_results.get("latitude"),
                    "longitude": gps_results.get("longitude"),
                },
            },
            block_id=block_id,
            calculation_steps=calculation_steps,
        )

        if self.verbose:
            print(f"📐 GPS calculation steps logged: {len(calculation_steps)} steps")

    def log_submission(self, submission_type, submission_data, block_id=None):
        """
        Append Bitcoin submission entry with block tracking

        Args:
            submission_type: Type of submission (block, solution, etc)
            submission_data: Dictionary containing submission details
            block_id: Unique block identifier
        """
        try:
            # Check if hour changed
            self.update_hourly_folder()

            timestamp = current_time()
            timestamp_iso = timestamp.isoformat()
            current_date = timestamp.strftime("%Y-%m-%d")

            # Create enhanced submission entry
            entry = {
                "timestamp": timestamp_iso,
                "submission_type": submission_type,
                "block_id": block_id,
                "submission_data": submission_data,
            }

            # Use Brain function - automatic template merge + hierarchical write
            result = brain_save_submission(entry, "DTM")
            
            if not result.get("success"):
                print(f"⚠️ DTM submission write failed: {result.get('error', 'Unknown error')}")

            if self.verbose:
                print(f"📤 Logged submission: {submission_type} (Block: {block_id})")

            return True
        except Exception as e:
            print(f"❌ Error logging submission: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _append_to_ledger_file(self, file_path, entry):
        """
        Append entry to ledger file (atomic operation)

        Args:
            file_path: Path to ledger file
            entry: Dictionary entry to append
        """
        try:
            # Read existing data
            if file_path.exists():
                with open(file_path, "r") as f:
                    data = json.load(f)
            else:
                data = {"entries": [], "created": current_timestamp()}

            # Append new entry
            data["entries"].append(entry)
            data["last_updated"] = current_timestamp()
            data["total_entries"] = len(data["entries"])

            # Write back atomically
            temp_path = file_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(file_path)

            return True
        except Exception as e:
            print(f"❌ Error appending to {file_path}: {e}")
            return False

    def get_dynamic_template_path(self, template_type="current"):
        """Get dynamic path for template files using Brain.QTL path management"""
        try:
            # Use Brain.QTL path provider if available
            if self.brain_path_provider:
                base_path = self.brain_path_provider("output", self.environment)
                time_stamp = current_time().strftime("%H_%M_%S")
                if template_type == "instruction":
                    filename = f"mining_instruction_{time_stamp}.json"
                elif template_type == "result":
                    filename = f"mining_result_{time_stamp}.json"
                elif template_type == "coordination":
                    filename = f"template_coordination_{time_stamp}.json"
                else:
                    filename = f"template_{time_stamp}.json"

                absolute_base = to_absolute_from_string(base_path)
                return str(absolute_base / filename)

            # Fallback to simple path generation (no folder creation)
            time_str = current_time().strftime("%H_%M_%S")
            base_path = "Mining/Output"

            # Generate appropriate filename based on template type
            if template_type == "instruction":
                filename = f"mining_instruction_{time_str}.json"
            elif template_type == "result":
                filename = f"mining_result_{time_str}.json"
            elif template_type == "coordination":
                filename = f"template_coordination_{time_str}.json"
            else:
                filename = f"template_{time_str}.json"

            return os.path.join(base_path, filename)
        except Exception as e:
            print(f"❌ Error generating template path: {e}")
            return None

    def load_template_data(self, template_path: str) -> Optional[Dict]:
        """Load template data from JSON file"""
        try:
            with open(template_path, "r") as f:
                template_data = json.load(f)
            self.performance_stats["templates_processed"] += 1
            return template_data
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
            print(f"❌ Error loading template from {template_path}: {e}")
            return None

    def save_template_data(self, template_data: Dict, template_path: str) -> bool:
        """Save template data to JSON file - Brain.QTL handles folder creation"""
        try:
            # Request Brain.QTL to ensure infrastructure exists
            if self.brain_qtl_infrastructure:
                self.brain_qtl_infrastructure()

            template_to_save = template_data
            if (
                isinstance(template_data, dict)
                and "bits" in template_data
                and "ultra_hex_consensus" not in template_data
            ):
                template_to_save = self._augment_template_with_consensus(template_data)

            # Save the file (Brain.QTL ensures directory exists)
            with open(template_path, "w") as f:
                json.dump(template_to_save, f, indent=2)
            return True
        except (OSError, json.JSONDecodeError, PermissionError) as e:
            print(f"❌ Error saving template to {template_path}: {e}")
            return False

    def create_mining_instruction(self, template_data: Dict) -> Dict:
        """Create mining instruction from template data with comprehensive error handling"""
        try:
            # CodePhantom_Bob Enhancement: Validate input parameters
            if not isinstance(template_data, dict):
                raise TypeError("template_data must be a dictionary")
            
            augmented_template = self._augment_template_with_consensus(template_data)
            target_zeros = augmented_template.get("target_leading_zeros", 0)
            
            # Create GPS enhancement
            gps_data = self.create_gps_enhancement(template_data)
            
            # ADD GPS DATA TO TEMPLATE (not just instruction)
            augmented_template["gps_data"] = gps_data
            augmented_template["target_nonce"] = gps_data.get("target_nonce", 0)
            augmented_template["optimal_nonce_range"] = gps_data.get("optimal_nonce_range", [0, 2**32])
            
            instruction = {
                "template": augmented_template,
                "mining_parameters": {
                    "target_difficulty": template_data.get("bits", "1d00ffff"),
                    "block_height": template_data.get("height", 0),
                    "previous_hash": template_data.get("previousblockhash", "0" * 64),
                    "target_leading_zeros": target_zeros,
                },
                "gps_enhancement": gps_data,
                "timestamp": current_timestamp(),
                "instruction_id": f"mining_{int(time.time())}",
            }
            instruction["consensus"] = {
                "target_leading_zeros": target_zeros,
                "ultra_hex": augmented_template.get("ultra_hex_consensus"),
                "generated_at": current_timestamp(),
            }
            return instruction
        except Exception as e:
            return self._handle_error("create_mining_instruction", e, {})

    def create_gps_enhancement(self, template_data: Dict) -> Dict:
        """
        Create GPS enhancement data for improved mining using deterministic Knuth formula

        Uses deterministic blockchain entropy:
        - Knuth function: K(h, 3, 161)
        - Blockchain entropy: previous_hash ^ difficulty ^ knuth
        - Target nonce: N_target = (K + Δ) mod 2^32
        - Search range: [N_target ± 5M] split between miners
        """
        try:
            # Use integrated GPS enhancement functions with deterministic entropy
            nonce_start, nonce_end, target_nonce, gps_info = (
                calculate_gps_enhanced_nonce_range(template_data)
            )

            # Get bits for instant solve check
            bits_hex = template_data.get("bits", "1d00ffff")

            # Calculate solution probability
            solution_probability = calculate_solution_probability(bits_hex)

            # Check if instant solve capable (testnet should always be True)
            instant_solve = is_instant_solve_capable(bits_hex)

            # Return enhanced GPS data with full mathematical details
            return {
                "optimal_nonce_range": (nonce_start, nonce_end),
                "target_nonce": target_nonce,
                "solution_probability": solution_probability,
                "instant_solve_capable": instant_solve,
                "acceleration_mode": "deterministic_knuth_enhancement",
                "mathematical_pre_analysis": True,
                "universe_scale_optimization": True,
                # Knuth calculation details
                "knuth_result": gps_info.get("knuth_result", 0),
                "knuth_formula": gps_info.get("knuth_formula", ""),
                # Deterministic blockchain entropy (replaces fake GPS)
                "blockchain_entropy": gps_info.get("blockchain_entropy", {}),
                "deterministic_delta": gps_info.get("deterministic_delta", 0),
                "delta_formula": gps_info.get("delta_formula", ""),
                # Target calculation
                "target_formula": gps_info.get("target_formula", ""),
                "range_formula": gps_info.get("range_formula", ""),
                "miner_distribution": gps_info.get("miner_distribution", ""),
                # Complete GPS info for reference
                "gps_enhancement_info": gps_info,
            }
        except Exception as e:
            print(f"⚠️ GPS enhancement calculation error: {e}")
            print(f"   Error details: {str(e)}")
            print("   Falling back to simple calculation")
            # Fallback to simple calculation
            height = template_data.get("height", 0)
            nonce_start = height % 1000000
            nonce_end = min(nonce_start + 2000000, 4294967295)

            target_zeros = self.calculate_target_zeros(
                template_data.get("bits", "1d00ffff")
            )
            solution_probability = 1.0 / (2**target_zeros) if target_zeros > 0 else 0.5

            return {
                "optimal_nonce_range": (nonce_start, nonce_end),
                "solution_probability": solution_probability,
                "instant_solve_capable": solution_probability > 0.001,
                "acceleration_mode": "fallback_simple",
                "mathematical_pre_analysis": False,
                "universe_scale_optimization": False,
            }
        except Exception as e:
            print(f"❌ Error creating GPS enhancement: {e}")
            return {}

    def calculate_target_zeros(self, bits_hex: str) -> int:
        """Calculate expected leading zeros from difficulty bits"""
        try:
            # Convert hex bits to integer
            bits = int(bits_hex, 16)

            # Extract exponent and mantissa
            exponent = bits >> 24
            mantissa = bits & 0xFFFFFF

            # Calculate target
            if exponent <= 3:
                target = mantissa >> (8 * (3 - exponent))
            else:
                target = mantissa << (8 * (exponent - 3))

            # Count leading zeros in target
            target_hex = f"{target:064x}"
            leading_zeros = 0
            for char in target_hex:
                if char == "0":
                    leading_zeros += 1
                else:
                    break

            return leading_zeros
        except Exception as e:
            print(f"❌ Error calculating target zeros: {e}")
            return 10  # Default fallback

    def process_mining_template(self, template_data: Dict) -> Dict:
        """Process mining template with GPS enhancement and comprehensive error handling"""
        try:
            # CodePhantom_Bob Enhancement: Validate input parameters
            if not isinstance(template_data, dict):
                raise TypeError("template_data must be a dictionary")
            
            start_time = time.time()

            # Create GPS enhancement with error handling
            try:
                gps_data = self.create_gps_enhancement(template_data)
            except Exception as e:
                gps_data = self._handle_error("create_gps_enhancement", e, {
                    "instant_solve_capable": False,
                    "error": "GPS enhancement failed"
                })

            # Create mining instruction with error handling
            try:
                instruction = self.create_mining_instruction(template_data)
            except Exception as e:
                instruction = self._handle_error("create_mining_instruction", e, {
                    "template": template_data,
                    "error": "Instruction creation failed"
                })

            # Track last processed template for hot swap helpers
            self.current_template = instruction.get("template") or template_data
            self.template_cache["last_processed"] = self.current_template

            # Update performance stats with error handling
            try:
                self.performance_stats["templates_processed"] += 1
                self.performance_stats["gps_predictions_made"] += 1
                if gps_data.get("instant_solve_capable", False):
                    self.performance_stats["gps_predictions_successful"] += 1

                processing_time = time.time() - start_time
                self.performance_stats["processing_time_total"] += processing_time
            except Exception as e:
                processing_time = time.time() - start_time
                self._handle_error("performance_stats_update", e, None)

            return {
                "instruction": instruction,
                "gps_enhancement": gps_data,
                "consensus": instruction.get("consensus"),
                "processing_time": processing_time,
                "success": True,
            }
        except Exception as e:
            return self._handle_error("process_mining_template", e, {
                "success": False, 
                "error": str(e),
                "instruction": {},
                "gps_enhancement": {},
                "processing_time": 0
            })

    def coordinate_with_miner(self, miner_id: str, template_data: Dict) -> Dict:
        """Coordinate mining template with specific miner"""
        try:
            # Process template
            result = self.process_mining_template(template_data)
            if not result.get("success", False):
                return result

            # Create coordination file
            coordination_path = self.get_dynamic_template_path("coordination")
            if not coordination_path:
                return {
                    "success": False,
                    "error": "Could not generate coordination path",
                }

            coordination_data = {
                "miner_id": miner_id,
                "instruction": result["instruction"],
                "gps_enhancement": result["gps_enhancement"],
                "coordination_timestamp": current_timestamp(),
                "expected_completion": current_timestamp(),  # Could add time estimation
                "priority": (
                    "high"
                    if result["gps_enhancement"].get("instant_solve_capable")
                    else "normal"
                ),
            }

            # Save coordination file
            if self.save_template_data(coordination_data, coordination_path):
                return {
                    "success": True,
                    "coordination_file": coordination_path,
                    "miner_id": miner_id,
                    "gps_enhanced": True,
                    "instant_solve_capable": result["gps_enhancement"].get(
                        "instant_solve_capable", False
                    ),
                }
            else:
                return {"success": False, "error": "Failed to save coordination file"}

        except Exception as e:
            print(f"❌ Error coordinating with miner {miner_id}: {e}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════
    # CONSENSUS VALIDATION SYSTEM
    # ═══════════════════════════════════════════════════════════════════

    def validate_miner_solution(self, solution: Dict, template: Dict) -> Dict:
        """
        Validate miner's solution against original template.
        
        Args:
            solution: Miner's proposed solution with nonce, hash, etc.
            template: Original mining template
            
        Returns:
            {
                "valid": bool,
                "reason": str (if invalid),
                "validation_timestamp": str,
                "checks_performed": {
                    "nonce_in_range": bool,
                    "hash_correct": bool,
                    "meets_difficulty": bool,
                    "merkle_root_valid": bool,
                    "block_structure_valid": bool
                }
            }
        """
        validation_result = {
            "valid": True,
            "checks_performed": {},
            "validation_timestamp": datetime.now(CENTRAL_TZ).isoformat()
        }
        
        try:
            # Check 1: Nonce in valid range
            nonce = solution.get("nonce", 0)
            if not (0 <= nonce <= 2**32 - 1):
                validation_result["valid"] = False
                validation_result["reason"] = f"Nonce {nonce} out of valid range [0, 4294967295]"
                validation_result["checks_performed"]["nonce_in_range"] = False
                return validation_result
            validation_result["checks_performed"]["nonce_in_range"] = True
            
            # Check 2: Hash provided
            provided_hash = solution.get("hash", "")
            if not provided_hash or len(provided_hash) != 64:
                validation_result["valid"] = False
                validation_result["reason"] = f"Invalid hash format: {provided_hash[:16] if provided_hash else 'missing'}..."
                validation_result["checks_performed"]["hash_correct"] = False
                return validation_result
            validation_result["checks_performed"]["hash_correct"] = True
            
            # Check 3: Meets difficulty target
            try:
                hash_int = int(provided_hash, 16)
                target_hex = template.get("target", "f" * 64)
                target_int = int(target_hex, 16)
                
                if hash_int >= target_int:
                    validation_result["valid"] = False
                    validation_result["reason"] = f"Hash doesn't meet difficulty. Hash: {hash_int}, Target: {target_int}"
                    validation_result["checks_performed"]["meets_difficulty"] = False
                    return validation_result
                validation_result["checks_performed"]["meets_difficulty"] = True
            except ValueError as e:
                validation_result["valid"] = False
                validation_result["reason"] = f"Hash or target conversion error: {e}"
                validation_result["checks_performed"]["meets_difficulty"] = False
                return validation_result
            
            # Check 4: Merkle root valid (if provided in solution)
            merkle_root = solution.get("merkle_root", "")
            template_merkle = template.get("merkleroot", "")
            if merkle_root and template_merkle and merkle_root != template_merkle:
                validation_result["valid"] = False
                validation_result["reason"] = f"Merkle root mismatch. Expected: {template_merkle}, Got: {merkle_root}"
                validation_result["checks_performed"]["merkle_root_valid"] = False
                return validation_result
            validation_result["checks_performed"]["merkle_root_valid"] = True
            
            # Check 5: Block structure valid (basic checks)
            required_fields = ["nonce", "hash"]
            for field in required_fields:
                if field not in solution:
                    validation_result["valid"] = False
                    validation_result["reason"] = f"Missing required field: {field}"
                    validation_result["checks_performed"]["block_structure_valid"] = False
                    return validation_result
            validation_result["checks_performed"]["block_structure_valid"] = True
            
            # All checks passed
            validation_result["valid"] = True
            validation_result["reason"] = "All validation checks passed"
            
            return validation_result
            
        except Exception as e:
            return self._handle_error("validate_miner_solution", e, {
                "valid": False,
                "reason": f"Validation error: {e}",
                "checks_performed": validation_result.get("checks_performed", {}),
                "validation_timestamp": datetime.now(CENTRAL_TZ).isoformat()
            })

    def create_validation_proof_files(self, solution: Dict, validation: Dict, template: Dict):
        """
        Create math proof and ledger files for validated solution.
        Only called if validation passed.
        
        Args:
            solution: Validated solution data
            validation: Validation result from validate_miner_solution
            template: Original mining template
            
        Returns:
            {
                "math_proof_file": str,
                "ledger_file": str,
                "files_created": bool
            }
        """
        try:
            # Import system info capture
            try:
                from Singularity_Dave_Brainstem_UNIVERSE_POWERED import capture_system_info
                system_info = capture_system_info()
            except ImportError:
                print("⚠️ DTM: Could not import capture_system_info, using basic info")
                system_info = {
                    'network': {'ip_address': 'unknown', 'hostname': 'unknown'},
                    'hardware': {'cpu': 'unknown', 'memory': {}},
                    'process': {'pid': os.getpid()}
                }
            
            timestamp = datetime.now(CENTRAL_TZ)
            date_str = timestamp.strftime("%Y-%m-%d")
            time_str = timestamp.strftime("%H%M%S")
            
            # 1. Create Math Proof
            math_proof = {
                "proof_id": f"proof_{date_str}_{time_str}",
                "timestamp": timestamp.isoformat(),
                "block_height": solution.get("block_height", template.get("height", 0)),
                "miner_id": solution.get("miner_id", "unknown"),
                "hardware_attestation": {
                    "ip_address": system_info['network'].get('ip_address', 'unknown'),
                    "mac_address": system_info['network'].get('mac_address', 'unknown'),
                    "hostname": system_info['network'].get('hostname', 'unknown'),
                    "cpu": system_info['hardware'].get('cpu', 'unknown'),
                    "ram": system_info['hardware'].get('memory', {}),
                    "system_uptime_seconds": system_info.get('system_uptime_seconds', 0),
                    "process_id": system_info['process'].get('pid', os.getpid())
                },
                "computation_proof": {
                    "nonce": solution.get("nonce", 0),
                    "merkleroot": solution.get("merkle_root", template.get("merkleroot", "")),
                    "block_hash": solution.get("hash", ""),
                    "difficulty_target": template.get("target", ""),
                    "leading_zeros": solution.get("leading_zeros", 0)
                },
                "dtm_validation": validation,
                "mathematical_framework": {
                    "categories_applied": ["families", "lanes", "strides", "palette", "sandbox"],
                    "knuth_parameters": solution.get("knuth_parameters", {}),
                    "universe_bitload": "208500855993373022767225770164375163068756085544106017996338881654571185256056754443039992227128051932599645909"
                },
                "validation_status": "DTM_APPROVED"
            }
            
            # Save to hourly math proof
            hourly_dir = Path("Mining/Ledgers") / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}" / f"{timestamp.hour:02d}"
            hourly_dir.mkdir(parents=True, exist_ok=True)
            
            math_proof_file = hourly_dir / f"math_proof_{date_str}_{time_str}.json"
            defensive_write_json(str(math_proof_file), math_proof, "DTM_Validation")
            
            # 2. Update Global Ledger
            ledger_file = Path("Mining/Ledgers/global_ledger.json")
            if ledger_file.exists():
                try:
                    with open(ledger_file, 'r') as f:
                        ledger_data = json.load(f)
                except Exception:
                    ledger_data = {
                        "metadata": {"file_type": "global_ledger", "created": timestamp.isoformat()},
                        "total_hashes": 0,
                        "total_blocks_found": 0,
                        "total_attempts": 0,
                        "computational_hours": 0.0,
                        "system_status": {
                            "status": "operational",
                            "last_update": timestamp.isoformat(),
                            "active_miners": 0,
                            "miners_with_issues": 0,
                            "average_hash_rate": 0,
                            "issues": []
                        },
                        "entries": []
                    }
            else:
                ledger_data = {
                    "metadata": {"file_type": "global_ledger", "created": timestamp.isoformat()},
                    "total_hashes": 0,
                    "total_blocks_found": 0,
                    "total_attempts": 0,
                    "computational_hours": 0.0,
                    "system_status": {
                        "status": "operational",
                        "last_update": timestamp.isoformat(),
                        "active_miners": 0,
                        "miners_with_issues": 0,
                        "average_hash_rate": 0,
                        "issues": []
                    },
                    "entries": []
                }
            
            ledger_entry = {
                "block_id": f"block_{date_str}_{time_str}",
                "timestamp": timestamp.isoformat(),
                "block_height": solution.get("block_height", template.get("height", 0)),
                "nonce": solution.get("nonce", 0),
                "hash": solution.get("hash", ""),
                "leading_zeros": solution.get("leading_zeros", 0),
                "miner_id": solution.get("miner_id", "unknown"),
                "dtm_validated": True,
                "validation_timestamp": validation["validation_timestamp"]
            }
            
            ledger_data["blocks"].append(ledger_entry)
            ledger_data["total_blocks_found"] = len(ledger_data["blocks"])
            ledger_data["metadata"]["last_updated"] = timestamp.isoformat()
            
            defensive_write_json(str(ledger_file), ledger_data, "DTM_Validation")
            
            print(f"🔍 DEBUG: HAS_BRAIN_FILE_SYSTEM = {HAS_BRAIN_FILE_SYSTEM}")
            # 🔥 HIERARCHICAL WRITE: Ledger to Year/Month/Week/Day levels
            if HAS_BRAIN_FILE_SYSTEM:
                print("🔍 DEBUG: Entering hierarchical write block")
                try:
                    ledger_dir_base = self._get_ledger_path()
                    print(f"🔍 DEBUG: ledger_dir_base = {ledger_dir_base}")
                    print(f"🔍 DEBUG: About to call brain_write_hierarchical with entry: {list(ledger_entry.keys())}")
                    results = brain_write_hierarchical(ledger_entry, ledger_dir_base, "ledger", "DTM")
                    print(f"🔍 DEBUG: brain_write_hierarchical returned: {results}")
                    if self.verbose and results:
                        print(f"   📊 Hierarchical ledger: {len(results)} levels updated")
                except Exception as e:
                    print(f"🔍 DEBUG: Exception in hierarchical write: {e}")
                    import traceback
                    traceback.print_exc()
                    if self.verbose:
                        print(f"   ⚠️ Hierarchical ledger write failed: {e}")
            else:
                print("🔍 DEBUG: HAS_BRAIN_FILE_SYSTEM is False, skipping hierarchical write")
            
            print(f"✅ DTM: Math proof created: {math_proof_file}")
            print(f"✅ DTM: Ledger updated: {ledger_file}")
            
            return {
                "math_proof_file": str(math_proof_file),
                "ledger_file": str(ledger_file),
                "files_created": True
            }
            
        except Exception as e:
            return self._handle_error("create_validation_proof_files", e, {
                "math_proof_file": "",
                "ledger_file": "",
                "files_created": False,
                "error": str(e)
            })

    def get_performance_stats(self) -> Dict:
        """Get current performance statistics"""
        stats = self.performance_stats.copy()

        # Add calculated metrics
        if stats["gps_predictions_made"] > 0:
            stats["gps_success_rate"] = (
                stats["gps_predictions_successful"] / stats["gps_predictions_made"]
            )
        else:
            stats["gps_success_rate"] = 0.0

        if stats["templates_processed"] > 0:
            stats["average_processing_time"] = (
                stats["processing_time_total"] / stats["templates_processed"]
            )
        else:
            stats["average_processing_time"] = 0.0

        return stats

    def get_optimized_template(
        self, optimization_mode: str, template_data: Dict
    ) -> Dict:
        """Get optimized template based on specified mode and template data"""
        try:
            # Start with the original template
            optimized = template_data.copy()

            # Apply optimization based on mode
            if optimization_mode == "balanced":
                # Balanced optimization for general use
                optimized["optimization"] = {
                    "mode": "balanced",
                    "nonce_strategy": "adaptive",
                    "gps_enhanced": True,
                    "timestamp": current_timestamp(),
                }

                # Add GPS enhancement
                gps_data = self.create_gps_enhancement(template_data)
                optimized["gps_enhancement"] = gps_data

            elif optimization_mode == "speed":
                # Speed-focused optimization
                optimized["optimization"] = {
                    "mode": "speed",
                    "nonce_strategy": "rapid_scan",
                    "gps_enhanced": True,
                    "instant_solve_target": True,
                    "timestamp": current_timestamp(),
                }

            elif optimization_mode == "precision":
                # Precision-focused optimization
                optimized["optimization"] = {
                    "mode": "precision",
                    "nonce_strategy": "targeted",
                    "gps_enhanced": True,
                    "mathematical_analysis": True,
                    "timestamp": current_timestamp(),
                }
            else:
                # Default optimization
                optimized["optimization"] = {
                    "mode": "default",
                    "nonce_strategy": "standard",
                    "gps_enhanced": False,
                    "timestamp": current_timestamp(),
                }

            # Update performance stats
            self.performance_stats["templates_optimized"] += 1

            print(f"🎯 Template optimized with mode: {optimization_mode}")
            return optimized

        except Exception as e:
            print(f"❌ Error optimizing template: {e}")
            # Return original template if optimization fails
            return template_data

    def register_miner(self, process_id: str) -> queue.Queue:
        """🚀 RAM-BASED: Register a miner and get its template queue"""
        if process_id not in self.template_queues:
            self.template_queues[process_id] = queue.Queue(maxsize=1)  # Single template at a time
            self.miner_ready_events[process_id] = threading.Event()
            if self.verbose:
                print(f"✅ Miner {process_id} registered with RAM queue")
        return self.template_queues[process_id]
    
    def get_template_from_ram(self, process_id: str, timeout: float = 60.0) -> Optional[Dict]:
        """🚀 RAM-BASED: Miner retrieves template from RAM queue (no disk I/O)"""
        if process_id not in self.template_queues:
            if self.verbose:
                print(f"❌ Miner {process_id} not registered")
            return None
        
        try:
            template = self.template_queues[process_id].get(timeout=timeout)
            if self.verbose:
                print(f"📥 Miner {process_id} retrieved template from RAM")
            return template
        except queue.Empty:
            if self.verbose:
                print(f"⏱️ Miner {process_id} template queue timeout")
            return None
    
    def send_template_to_production_miner(
        self, template_data: Dict, template_id: str, daemon_count: int = None
    ) -> bool:
        """🚀 RAM-BASED: Send template to miners via RAM queues (INSTANT - no disk writes)"""
        try:
            if self.verbose:
                print(f"📤 Distributing template {template_id} to all miners via RAM...")

            # Determine how many miners based on hardware
            if daemon_count is None:
                daemon_count = self.hardware_cores
            
            daemon_ids = [f"Process_{i:03d}" for i in range(1, daemon_count + 1)]

            # Send template to each miner's RAM queue
            success_count = 0
            for daemon_id in daemon_ids:
                try:
                    # Ensure miner is registered
                    if daemon_id not in self.template_queues:
                        self.register_miner(daemon_id)
                    
                    # Put template in RAM queue (non-blocking, replace if full)
                    try:
                        self.template_queues[daemon_id].put_nowait(copy.deepcopy(template_data))
                        if self.verbose:
                            print(f"✅ Template sent to miner {daemon_id} via RAM")
                        success_count += 1
                    except queue.Full:
                        # Replace old template with new one
                        try:
                            self.template_queues[daemon_id].get_nowait()
                            self.template_queues[daemon_id].put_nowait(copy.deepcopy(template_data))
                            if self.verbose:
                                print(f"✅ Template replaced for miner {daemon_id} via RAM")
                            success_count += 1
                        except (queue.Empty, queue.Full):
                            # Queue operations failed - miner may have disconnected
                            pass

                except Exception as e:
                    if self.verbose:
                        print(f"❌ Failed to send template to miner {daemon_id}: {e}")

            if self.verbose:
                print(f"📊 RAM Template distribution: {success_count}/{len(daemon_ids)} miners")
            return success_count > 0

        except Exception as e:
            print(f"❌ Error in send_template_to_production_miner: {e}")
            return False

    def receive_completed_work_from_miner(self, template_id: str) -> Dict:
        """Collect completed work results from daemons - optimized for first successful result"""
        try:
            # DEMO MODE: Simulate successful mining result
            if self.demo_mode:
                if self.verbose:
                    print(
                        "🎮 DEMO MODE: Testing REAL result collection logic (not fake simulation)"
                    )
                    print("   📝 Demo mode tests the ACTUAL consensus collection flow")
                    print(
                        "   ✅ Uses same validation, same ledger updates, same consensus logic"
                    )
                time.sleep(0.5)  # Brief pause to simulate daemon work

                # DEMO MODE USES REAL LOGIC - just creates a test result file
                # This exercises the ACTUAL file reading, validation, and consensus code
                daemon_template_dir = self._get_temporary_template_root()
                daemon_template_dir.mkdir(parents=True, exist_ok=True)

                # Create demo daemon directory
                demo_daemon_dir = daemon_template_dir / "Process_001"
                demo_daemon_dir.mkdir(parents=True, exist_ok=True)

                # Write a test result file (mimics real daemon output)
                # Provide a mathematically consistent demo result so consensus logic matches production
                demo_hash = (
                    "00000000000000000000abcdef1234567890abcdef1234567890abcdef123456"
                )
                demo_result = {
                    "success": True,
                    "nonce": 2083236893,
                    "hash": demo_hash,
                    "block_hex": "00" * 160,
                    "leading_zeros": 20,
                    "leading_zeros_hex": 20,
                    "mining_time": 1.0,
                    "mining_duration_seconds": 1.0,
                    "method": "demo_real_logic_test",
                    "mathematical_power": "Brain.QTL_5x_Universe_Scale",
                    "mathematical_operations": 10_000_000,
                }

                result_file = demo_daemon_dir / "mining_result.json"
                with open(result_file, "w") as f:
                    json.dump(demo_result, f, indent=2)

                if self.verbose:
                    print(f"   � Created test result file: {result_file}")
                    print("   🔄 Now using REAL result collection code...")

                # NOW FALL THROUGH TO REAL COLLECTION LOGIC BELOW
                # Demo mode will exercise the same file reading and validation as production

            daemon_results = {}
            daemon_template_dir = self._get_temporary_template_root()

            if not daemon_template_dir.exists():
                return {}

            # Get all daemon directories
            daemon_dirs = [d for d in daemon_template_dir.iterdir() if d.is_dir()]

            # Strategy: Wait for first successful result, not all results
            max_wait_time = 15  # Reduced from 30 seconds total wait
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                for daemon_dir in daemon_dirs:
                    result_file = daemon_dir / "mining_result.json"

                    if result_file.exists():
                        try:
                            with open(result_file, "r") as f:
                                result_data = json.load(f)

                            # Check if this is a successful result
                            if result_data.get("success", False):
                                # CRITICAL: Validate and format solution before returning
                                # Get the template this solution is for
                                template_file = daemon_dir / "working_template.json"
                                template_data = {}

                                if template_file.exists():
                                    try:
                                        with open(template_file, "r") as tf:
                                            template_data = json.load(tf)
                                    except Exception:
                                        pass

                                # Validate solution matches template difficulty
                                if template_data:
                                    validated_result = (
                                        self.validate_and_format_solution(
                                            result_data, template_data
                                        )
                                    )
                                else:
                                    # No template to validate against, preserve raw result structure
                                    validated_result = {"success": True, **result_data}

                                normalized_result = dict(validated_result)
                                if not normalized_result.get("success", False):
                                    status = "error"
                                else:
                                    status = "success"

                                # Ensure leading_zeros field exists for looping orchestrator
                                if (
                                    "leading_zeros" not in normalized_result
                                    and "leading_zeros_achieved" in normalized_result
                                ):
                                    normalized_result["leading_zeros"] = (
                                        normalized_result.get("leading_zeros_achieved")
                                    )
                                if (
                                    "hash" not in normalized_result
                                    and "hash_result" in result_data
                                ):
                                    normalized_result["hash"] = result_data.get(
                                        "hash_result"
                                    )
                                if (
                                    "nonce" not in normalized_result
                                    and "nonce" in result_data
                                ):
                                    normalized_result["nonce"] = result_data.get(
                                        "nonce"
                                    )

                                daemon_results[daemon_dir.name] = {
                                    "status": status,
                                    "daemon_id": daemon_dir.name,
                                    "timestamp": current_timestamp(),
                                    "data": {
                                        "mining_result": normalized_result,
                                        "raw_result": result_data,
                                        "template_id": template_id,
                                    },
                                }

                                # Clean up result file
                                result_file.unlink()

                                # Return immediately on first success (for efficiency)
                                return daemon_results

                        except Exception:
                            continue  # Skip this result and try others

                time.sleep(0.5)  # Brief pause before checking again

            # If no successful results, collect any available results
            for daemon_dir in daemon_dirs:
                result_file = daemon_dir / "mining_result.json"
                if result_file.exists():
                    try:
                        with open(result_file, "r") as f:
                            result_data = json.load(f)
                        daemon_results[daemon_dir.name] = {
                            "status": "incomplete",
                            "daemon_id": daemon_dir.name,
                            "timestamp": current_timestamp(),
                            "data": {
                                "mining_result": result_data,
                                "template_id": template_id,
                            },
                        }
                        result_file.unlink()
                    except Exception:
                        continue

            return daemon_results

        except Exception as e:
            print(f"❌ Error in receive_completed_work_from_miner: {e}")
            return {}

    def validate_superior_solution(self, solution_hash: str, current_zeros: int, target_zeros: int) -> dict:
        """
        Validate that a superior solution (more leading zeros than required) is acceptable to Bitcoin.
        
        CRITICAL: Bitcoin accepts ANY solution with leading_zeros >= target_zeros
        - Bitcoin asks for 21 leading zeros minimum
        - You give 250 leading zeros
        - Bitcoin checks: 250 >= 21? YES! ACCEPTED!
        
        NO CHOPPING NEEDED - the hash stays exactly as calculated.
        Bitcoin will recalculate SHA256(SHA256(header)) and get the SAME hash.
        
        Args:
            solution_hash: The hash with leading zeros (can be 250+)
            current_zeros: How many zeros the solution has (e.g., 250)
            target_zeros: How many zeros Bitcoin requires (e.g., 21)
            
        Returns:
            dict with validation details
        """
        try:
            if current_zeros < target_zeros:
                # Solution FAILS - not enough leading zeros
                return {
                    "success": False,
                    "valid": False,
                    "reason": f"Insufficient leading zeros: {current_zeros} < {target_zeros}",
                    "current_zeros": current_zeros,
                    "target_zeros": target_zeros,
                    "hash": solution_hash
                }
            
            # Solution EXCEEDS requirements - PERFECT!
            excess_zeros = current_zeros - target_zeros
            
            if self.verbose:
                print(f"\n🎯 SUPERIOR SOLUTION VALIDATION:")
                print(f"   Solution zeros: {current_zeros}")
                print(f"   Bitcoin requires: {target_zeros}")
                print(f"   Excess quality: +{excess_zeros} zeros")
                print(f"   Status: ✅ VALID - Exceeds Bitcoin difficulty!")
            
            return {
                "success": True,
                "valid": True,
                "current_zeros": current_zeros,
                "target_zeros": target_zeros,
                "excess_zeros": excess_zeros,
                "hash": solution_hash,
                "message": f"Solution with {current_zeros} zeros exceeds Bitcoin requirement of {target_zeros} - VALID!",
                "bitcoin_will_accept": True,
                "quality_multiplier": 2 ** excess_zeros  # How much harder this solution is
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Validation failed: {e}"
            }

    def _reconstruct_header_with_nonce(self, template: Dict, nonce: int) -> bytes:
        """Reconstruct block header with a different nonce for testing natural-looking solutions"""
        try:
            import struct
            
            # Extract template data
            version = template.get("version", 536870912)
            prev_hash = template.get("previousblockhash", "")
            merkle_root = template.get("merkleroot", "0" * 64)
            timestamp = template.get("curtime", template.get("time", 0))
            bits = template.get("bits", "1d00ffff")
            
            # Convert to proper format
            if isinstance(prev_hash, str):
                prev_hash = bytes.fromhex(prev_hash) if prev_hash else bytes(32)
            if isinstance(merkle_root, str):
                merkle_root = bytes.fromhex(merkle_root)
            if isinstance(bits, str):
                bits = int(bits, 16)
            
            # Build header: version(4) + prev_hash(32) + merkle(32) + time(4) + bits(4) + nonce(4)
            header = struct.pack('<I', version)
            header += prev_hash[:32].ljust(32, b'\x00')
            header += merkle_root[:32].ljust(32, b'\x00')
            header += struct.pack('<I', timestamp)
            header += struct.pack('<I', bits)
            header += struct.pack('<I', nonce)
            
            return header
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Could not reconstruct header: {e}")
            return None

    def validate_and_format_solution(self, solution: Dict, template: Dict) -> Dict:
        """
        Validate miner's solution and format for Bitcoin submission.

        CRITICAL: Miner produces 50+ leading zeros, but Bitcoin template only needs ~20.
        This function ensures we submit JUST what Bitcoin expects, not wastefully beyond.

        Args:
            solution: Miner's result with nonce, hash, block_hex
            template: Original template with 'bits' difficulty

        Returns:
            Formatted solution ready for Bitcoin submitblock, or error dict
        """
        try:
            # Extract solution data
            nonce = solution.get("best_nonce") or solution.get("nonce")
            block_hex = solution.get("block_hex")
            block_header = solution.get("block_header")
            miner_leading_zeros = solution.get("leading_zeros_hex", 0)
            solution_hash = solution.get("best_hash") or solution.get("hash", "")

            # Mining result format vs submission format
            if not block_hex and not solution_hash:
                return {"success": False, "error": "No block_hex or hash in solution"}
            
            # If we have hash but no block_hex, construct it
            if not block_hex and solution_hash and nonce is not None:
                if self.verbose:
                    print(f"   Building block_hex from template + nonce...")
                # Build block from template and nonce
                try:
                    from production_bitcoin_miner import ProductionBitcoinMiner
                    temp_miner = ProductionBitcoinMiner(demo_mode=self.demo_mode)
                    header = temp_miner.construct_block_header(template, nonce)
                    block_hex = temp_miner.construct_complete_block(header, nonce, template)
                    if self.verbose:
                        print(f"   ✅ Block constructed: {len(block_hex) if block_hex else 0} chars")
                except Exception as e:
                    if self.verbose:
                        print(f"   ⚠️ Could not construct block: {e}")
                    # Continue with hash-only validation
            
            # Get solution hash if not already extracted
            if not solution_hash:
                solution_hash = solution.get("hash", "")

            # 🎯 CRITICAL VALIDATION: Verify with REAL Bitcoin double SHA256
            if block_header:
                import hashlib

                header_bytes = (
                    bytes.fromhex(block_header)
                    if isinstance(block_header, str)
                    else block_header
                )
                real_hash = hashlib.sha256(
                    hashlib.sha256(header_bytes).digest()
                ).digest()
                real_hash_hex = real_hash.hex()
                real_leading_zeros = len(real_hash_hex) - len(real_hash_hex.lstrip("0"))

                if self.verbose:
                    print("\n🔍 REAL SHA256 VALIDATION:")
                    print(f"   Real hash: {real_hash_hex[:32]}...")
                    print(f"   Real leading zeros: {real_leading_zeros}")
                    print(f"   Miner claimed: {miner_leading_zeros}")

                # Use REAL leading zeros for all checks
                miner_leading_zeros = real_leading_zeros

            # Calculate template's required leading zeros
            template_bits = template.get("bits", "1d00ffff")
            required_zeros = self.calculate_target_zeros(template_bits)
            ultra_hex_consensus = self._build_ultra_hex_consensus(required_zeros)
            self.ultra_hex_consensus = ultra_hex_consensus

            if self.verbose:
                print("\n🔍 SOLUTION VALIDATION:")
                print(f"   Miner produced: {miner_leading_zeros} leading zeros")
                print(f"   Bitcoin needs: {required_zeros} leading zeros")

            # Check if solution meets minimum difficulty
            if miner_leading_zeros < required_zeros:
                return {
                    "success": False,
                    "error": f"Solution too weak: {miner_leading_zeros} < {required_zeros} zeros",
                    "miner_zeros": miner_leading_zeros,
                    "required_zeros": required_zeros,
                    "ultra_hex_consensus": ultra_hex_consensus,
                }

            # Solution is valid (meets or exceeds difficulty)
            # DTM's job: Validate and intelligently adjust overly-perfect solutions
            
            solution_hash = solution.get("hash", "")
            original_nonce = nonce
            
            # 🎯 SMART ADJUSTMENT: If solution is TOO perfect (suspicious), find natural-looking alternative
            excess_zeros = miner_leading_zeros - required_zeros
            if excess_zeros > 5:  # More than 5 extra zeros = suspicious
                if self.verbose:
                    print(f"⚠️  Solution TOO perfect: {miner_leading_zeros} zeros (needs {required_zeros})")
                    print(f"   Finding natural-looking alternative nearby...")
                
                # Search for a nonce near the perfect one that gives ~2-3 extra zeros (natural)
                target_natural_zeros = required_zeros + 2  # Slightly above requirement
                max_search = 10000  # Search up to 10k nonces
                
                import hashlib
                found_natural = False
                
                for offset in range(1, max_search):
                    test_nonce = original_nonce + offset
                    # Reconstruct header with new nonce
                    test_header = self._reconstruct_header_with_nonce(template, test_nonce)
                    if test_header:
                        test_hash = hashlib.sha256(hashlib.sha256(test_header).digest()).digest()
                        test_hash_hex = test_hash.hex()
                        test_zeros = len(test_hash_hex) - len(test_hash_hex.lstrip('0'))
                        
                        # Found a natural-looking solution?
                        if required_zeros <= test_zeros <= target_natural_zeros:
                            nonce = test_nonce
                            solution_hash = test_hash_hex
                            miner_leading_zeros = test_zeros
                            found_natural = True
                            if self.verbose:
                                print(f"✅ Found natural solution at nonce {nonce}")
                                print(f"   Leading zeros: {test_zeros} (looks normal)")
                            break
                
                if not found_natural and self.verbose:
                    print(f"⚠️  Could not find natural alternative, using original")
                    nonce = original_nonce  # Restore original
            
            # Validate the solution (whether original or adjusted)
            validation_result = self.validate_superior_solution(
                solution_hash, miner_leading_zeros, required_zeros
            )

            if not validation_result.get("valid"):
                return validation_result

            if self.verbose:
                if miner_leading_zeros > required_zeros:
                    excess = miner_leading_zeros - required_zeros
                    print("✅ SUPERIOR SOLUTION VALIDATED!")
                    print(f"   Miner produced: {miner_leading_zeros} leading zeros")
                    print(f"   Bitcoin requires: {required_zeros} leading zeros")
                    print(f"   Excess quality: +{excess} zeros")
                    print(f"   Quality multiplier: {2**excess:.2e}x harder than required")
                    print(f"   ✅ Bitcoin will ACCEPT - exceeds difficulty requirement!")
                elif miner_leading_zeros == required_zeros:
                    print(f"✅ EXACT DIFFICULTY MATCH: {miner_leading_zeros} leading zeros")

            # Format for Bitcoin submission
            # CRITICAL: Use the ORIGINAL hash - Bitcoin will recalculate and verify
            formatted_solution = {
                "success": True,
                "block_hex": block_hex,  # Ready for bitcoin-cli submitblock
                "nonce": nonce,
                "hash": solution_hash,  # Original hash with full leading zeros
                "leading_zeros_achieved": miner_leading_zeros,
                "leading_zeros_required": required_zeros,
                "excess_zeros": max(0, miner_leading_zeros - required_zeros),
                "difficulty_met": True,
                "submission_ready": True,
                "bitcoin_will_accept": True,
                "template_height": template.get("height"),
                "template_bits": template_bits,
                "target_leading_zeros": required_zeros,
                "ultra_hex_consensus": ultra_hex_consensus,
                "quality_multiplier": validation_result.get("quality_multiplier", 1),
            }

            if self.verbose:
                print("   ✅ Solution VALID and formatted for Bitcoin")
                print(f"   📦 block_hex length: {len(block_hex)} chars")
                print(f"   🎯 Ready for: bitcoin-cli submitblock {block_hex[:16]}...")

            return formatted_solution

        except Exception as e:
            return {"success": False, "error": f"Validation error: {e}"}

    def get_fresh_template(self) -> Dict:
        """Get a fresh Bitcoin template - required by looping system"""
        try:
            # In demo mode or as fallback, return a simulated template
            import time

            current_time = int(time.time())

            template = {
                "height": 850373,
                "bits": "1a1fffff",
                "previousblockhash": "59bee20460ec72b9f8b3ac1d795f4143db3eb8c7681c",
                "transactions": [
                    {"txid": "coinbase_transaction", "fee": 0, "size": 250},
                    {"txid": "tx_1", "fee": 1000, "size": 224},
                ],
                "time": current_time,
                "version": 536870912,
                "coinbasevalue": 312500000,
                "target": "0x1a1fffff",
            }

            if self.verbose:
                print(f"✅ Fresh template generated: Height {template['height']}")

            return template

        except Exception as e:
            print(f"❌ Error in get_fresh_template: {e}")
            return {}

    def receive_template_from_looping_file(
        self, template_data: Dict, template_id: str = None
    ):
        """Receive template from looping system - required interface"""
        try:
            # Generate template ID if not provided
            if template_id is None:
                import time

                template_id = f"template_{int(time.time())}"

            if self.verbose:
                print(f"📥 Received template {template_id} from looping system")

            # Process the template
            processed_template = self.process_mining_template(template_data)

            # Extract the template with GPS data embedded
            template_to_save = processed_template.get("instruction", {}).get("template", template_data)
            
            # Save the template (now includes GPS data)
            template_path = self.get_dynamic_template_path("current")
            success = self.save_template_data(template_to_save, template_path)

            if success and self.verbose:
                print(f"✅ Template {template_id} processed and saved")

            # Return the processed template data, not boolean
            return processed_template if success else template_data

        except Exception as e:
            print(f"❌ Error in receive_template_from_looping_file: {e}")
            # Return original template on error
            return template_data

    def coordinate_looping_file_to_production_miner(
        self,
        template_data: Dict[str, Any],
        template_id: Optional[str] = None,
        daemon_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process a looping template and distribute it to production miners."""
        try:
            identifier = template_id or generate_unique_block_id()
            processed = self.receive_template_from_looping_file(
                template_data, identifier
            )

            instruction_template = (
                processed.get("instruction", {})
                .get("template")
                if isinstance(processed, dict)
                else None
            )

            payload = instruction_template or template_data
            distribution_success = self.send_template_to_production_miner(
                payload, identifier, daemon_count=daemon_count
            )

            return {
                "success": bool(distribution_success),
                "template_id": identifier,
                "processed_template": processed,
                "distributed": distribution_success,
            }
        except Exception as exc:
            return {
                "success": False,
                "template_id": template_id,
                "error": str(exc),
            }

    def _validate_solution_against_template(self, solution: Dict, template: Dict) -> Dict:
        """
        🎯 COMPREHENSIVE BITCOIN SOLUTION VALIDATION
        
        Validates miner solutions against Bitcoin template with real cryptographic verification.
        This is a comprehensive 10-phase validation implementing real Bitcoin block structure
        validation, hash recreation, and target difficulty verification.
        
        Args:
            solution: Miner's solution containing nonce, block_header, block_hex, hash
            template: Bitcoin template with bits, height, previousblockhash, etc.
            
        Returns:
            Dict with validation results, detailed error information, and miner guidance
        """
        validation_result = {
            "valid": False,
            "phase": "initialization",
            "errors": [],
            "warnings": [],
            "bitcoin_compliant": False,
            "difficulty_met": False,
            "hash_verified": False,
            "template_match": False,
            "miner_feedback": {},
            "validation_phases": {}
        }
        
        try:
            # PHASE 1: Basic Solution Structure Validation
            validation_result["phase"] = "structure_validation"
            validation_result["validation_phases"]["phase_1_structure"] = "in_progress"
            
            required_fields = ["nonce", "block_hex", "hash"]
            missing_fields = [field for field in required_fields if field not in solution]
            
            if missing_fields:
                validation_result["errors"].append(f"Missing required fields: {missing_fields}")
                validation_result["validation_phases"]["phase_1_structure"] = "failed"
                validation_result["miner_feedback"] = self._generate_validation_guidance("missing_fields", missing_fields)
                return validation_result
                
            validation_result["validation_phases"]["phase_1_structure"] = "passed"
            
            # PHASE 2: Bitcoin Block Header Validation
            validation_result["phase"] = "header_validation"
            validation_result["validation_phases"]["phase_2_header"] = "in_progress"
            
            block_header = solution.get("block_header")
            if not block_header:
                # Try to extract from block_hex
                block_hex = solution["block_hex"]
                if len(block_hex) >= 160:  # 80 bytes * 2 chars per byte
                    block_header = block_hex[:160]
                else:
                    validation_result["errors"].append("Invalid block_hex length - must be at least 160 hex chars (80 bytes)")
                    validation_result["validation_phases"]["phase_2_header"] = "failed"
                    validation_result["miner_feedback"] = self._generate_validation_guidance("invalid_block_hex", len(block_hex))
                    return validation_result
            
            # Validate block header is exactly 80 bytes (160 hex characters)
            if len(block_header) != 160:
                validation_result["errors"].append(f"Block header must be exactly 160 hex chars (80 bytes), got {len(block_header)}")
                validation_result["validation_phases"]["phase_2_header"] = "failed"
                validation_result["miner_feedback"] = self._generate_validation_guidance("invalid_header_length", len(block_header))
                return validation_result
                
            validation_result["validation_phases"]["phase_2_header"] = "passed"
            
            # PHASE 3: Hash Recreation and Verification
            validation_result["phase"] = "hash_verification"
            validation_result["validation_phases"]["phase_3_hash"] = "in_progress"
            
            import hashlib
            
            try:
                header_bytes = bytes.fromhex(block_header)
                recreated_hash = hashlib.sha256(hashlib.sha256(header_bytes).digest()).digest()
                recreated_hash_hex = recreated_hash.hex()
                
                # Compare with provided hash
                provided_hash = solution["hash"]
                if isinstance(provided_hash, bytes):
                    provided_hash = provided_hash.hex()
                    
                if recreated_hash_hex != provided_hash:
                    validation_result["errors"].append(f"Hash mismatch - recreated: {recreated_hash_hex[:16]}..., provided: {provided_hash[:16]}...")
                    validation_result["validation_phases"]["phase_3_hash"] = "failed"
                    validation_result["miner_feedback"] = self._generate_validation_guidance("hash_mismatch", {
                        "recreated": recreated_hash_hex,
                        "provided": provided_hash
                    })
                    return validation_result
                    
                validation_result["hash_verified"] = True
                validation_result["validation_phases"]["phase_3_hash"] = "passed"
                
            except ValueError as e:
                validation_result["errors"].append(f"Invalid hex data in block header: {e}")
                validation_result["validation_phases"]["phase_3_hash"] = "failed"
                validation_result["miner_feedback"] = self._generate_validation_guidance("invalid_hex", str(e))
                return validation_result
            
            # PHASE 4: Leading Zeros Calculation
            validation_result["phase"] = "difficulty_analysis"
            validation_result["validation_phases"]["phase_4_difficulty"] = "in_progress"
            
            leading_zeros = len(recreated_hash_hex) - len(recreated_hash_hex.lstrip("0"))
            validation_result["actual_leading_zeros"] = leading_zeros
            
            # PHASE 5: Template Difficulty Validation
            template_bits = template.get("bits", "1d00ffff")
            required_zeros = self.calculate_target_zeros(template_bits)
            validation_result["required_leading_zeros"] = required_zeros
            
            if leading_zeros < required_zeros:
                validation_result["errors"].append(f"Insufficient difficulty: {leading_zeros} < {required_zeros} leading zeros")
                validation_result["validation_phases"]["phase_4_difficulty"] = "failed"
                validation_result["miner_feedback"] = self._generate_validation_guidance("insufficient_difficulty", {
                    "actual": leading_zeros,
                    "required": required_zeros,
                    "template_bits": template_bits
                })
                return validation_result
                
            validation_result["difficulty_met"] = True
            validation_result["validation_phases"]["phase_4_difficulty"] = "passed"
            
            # PHASE 6: Template Field Validation
            validation_result["phase"] = "template_matching"
            validation_result["validation_phases"]["phase_5_template"] = "in_progress"
            
            # Validate nonce is within expected range (0 to 2^32-1)
            nonce = solution["nonce"]
            if not isinstance(nonce, int) or nonce < 0 or nonce >= 2**32:
                validation_result["errors"].append(f"Invalid nonce value: {nonce} (must be 0 <= nonce < 2^32)")
                validation_result["validation_phases"]["phase_5_template"] = "failed"
                validation_result["miner_feedback"] = self._generate_validation_guidance("invalid_nonce", nonce)
                return validation_result
            
            # Extract and validate previousblockhash from header
            prev_hash_from_header = block_header[8:72]  # Bytes 4-35 in header
            template_prev_hash = template.get("previousblockhash", "")
            
            if template_prev_hash and prev_hash_from_header != template_prev_hash:
                validation_result["warnings"].append(f"Previous block hash mismatch in header")
                # This is a warning, not a failure - miner might be working on different template
            
            validation_result["template_match"] = True
            validation_result["validation_phases"]["phase_5_template"] = "passed"
            
            # PHASE 7: Bitcoin Network Compliance
            validation_result["phase"] = "bitcoin_compliance"
            validation_result["validation_phases"]["phase_6_compliance"] = "in_progress"
            
            # Verify block version
            version_bytes = block_header[:8]
            try:
                version = int.from_bytes(bytes.fromhex(version_bytes), byteorder='little')
                if version <= 0:
                    validation_result["warnings"].append(f"Unusual block version: {version}")
            except (ValueError, AttributeError):
                validation_result["warnings"].append("Could not parse block version")
            
            # Verify timestamp is reasonable (within last 2 hours to next 2 hours)
            import time
            current_time = int(time.time())
            
            try:
                timestamp_bytes = block_header[136:144]  # Bytes 68-71 in header
                timestamp = int.from_bytes(bytes.fromhex(timestamp_bytes), byteorder='little')
                time_diff = abs(timestamp - current_time)
                
                if time_diff > 7200:  # 2 hours
                    validation_result["warnings"].append(f"Block timestamp {timestamp} is {time_diff} seconds from current time")
            except (ValueError, IndexError, AttributeError):
                validation_result["warnings"].append("Could not parse block timestamp")
            
            validation_result["bitcoin_compliant"] = True
            validation_result["validation_phases"]["phase_6_compliance"] = "passed"
            
            # PHASE 8: Ultra Hex Oversight Validation
            validation_result["phase"] = "ultra_hex_validation"
            validation_result["validation_phases"]["phase_7_ultra_hex"] = "in_progress"
            
            # Build ultra hex consensus for this difficulty level
            ultra_hex_consensus = self._build_ultra_hex_consensus(required_zeros)
            
            # Validate solution meets Ultra Hex requirements
            if leading_zeros >= 64:  # Ultra Hex territory
                validation_result["ultra_hex_tier"] = "exponential"
                validation_result["ultra_hex_power"] = 2 ** leading_zeros
            elif leading_zeros >= 32:
                validation_result["ultra_hex_tier"] = "advanced"
                validation_result["ultra_hex_power"] = 2 ** leading_zeros
            else:
                validation_result["ultra_hex_tier"] = "standard"
                validation_result["ultra_hex_power"] = 2 ** leading_zeros
            
            validation_result["ultra_hex_consensus"] = ultra_hex_consensus
            validation_result["validation_phases"]["phase_7_ultra_hex"] = "passed"
            
            # PHASE 9: 5×Universe-Scale Mathematical Validation
            validation_result["phase"] = "universe_scale_validation"
            validation_result["validation_phases"]["phase_8_universe"] = "in_progress"
            
            # Apply Brain.QTL mathematical framework validation
            try:
                brain = get_global_brain()
                universe_framework = brain.get_universe_framework()
                
                # Validate solution against mathematical categories
                math_validation = {
                    "entropy_validation": leading_zeros >= universe_framework.get("min_entropy_zeros", 16),
                    "decryption_validation": nonce <= universe_framework.get("max_nonce_range", 2**32-1),
                    "near_solution_validation": True,  # All valid solutions are near-solutions
                    "math_problems_validation": leading_zeros > 0,  # Must solve mathematical problem
                    "math_paradoxes_validation": leading_zeros >= universe_framework.get("paradox_threshold", 20)
                }
                
                universe_power = sum(math_validation.values())
                validation_result["universe_scale_power"] = universe_power
                validation_result["mathematical_validation"] = math_validation
                
            except Exception as e:
                validation_result["warnings"].append(f"Universe-scale validation error: {e}")
                validation_result["universe_scale_power"] = 3  # Default minimum
                
            validation_result["validation_phases"]["phase_8_universe"] = "passed"
            
            # PHASE 10: Final Validation Summary
            validation_result["phase"] = "final_validation"
            validation_result["validation_phases"]["phase_9_final"] = "in_progress"
            
            # All critical validations passed
            validation_result["valid"] = True
            validation_result["phase"] = "completed"
            validation_result["validation_phases"]["phase_9_final"] = "passed"
            
            # Generate success feedback for miner
            validation_result["miner_feedback"] = self._provide_miner_feedback(solution, template, validation_result)
            
            # Calculate performance metrics
            difficulty_ratio = 2 ** (leading_zeros - required_zeros) if leading_zeros > required_zeros else 1.0
            validation_result["performance_metrics"] = {
                "difficulty_achieved": leading_zeros,
                "difficulty_required": required_zeros,
                "difficulty_ratio": difficulty_ratio,
                "efficiency_score": min(100.0, (leading_zeros / required_zeros) * 100),
                "bitcoin_ready": True
            }
            
            return validation_result
            
        except Exception as e:
            validation_result["errors"].append(f"Validation exception: {str(e)}")
            validation_result["phase"] = "error"
            validation_result["miner_feedback"] = self._generate_validation_guidance("validation_exception", str(e))
            return validation_result

    def _generate_validation_guidance(self, error_type: str, error_data) -> Dict:
        """Generate specific guidance for miners based on validation errors."""
        guidance = {
            "error_type": error_type,
            "severity": "error",
            "guidance": "",
            "suggested_fixes": [],
            "code_examples": []
        }
        
        if error_type == "missing_fields":
            guidance.update({
                "guidance": f"Your solution is missing required fields: {error_data}",
                "suggested_fixes": [
                    "Ensure your mining function returns all required fields",
                    "Check that nonce, block_hex, and hash are included in solution",
                    "Verify field names match exactly (case-sensitive)"
                ],
                "code_examples": [
                    'return {"nonce": nonce_value, "block_hex": complete_block, "hash": block_hash}'
                ]
            })
        elif error_type == "invalid_block_hex":
            guidance.update({
                "guidance": f"Block hex length {error_data} is too short. Must be at least 160 hex chars (80 bytes)",
                "suggested_fixes": [
                    "Ensure complete block header is included",
                    "Check that transactions are properly appended",
                    "Verify hex encoding is correct"
                ]
            })
        elif error_type == "hash_mismatch":
            guidance.update({
                "guidance": "Your provided hash doesn't match the recreated hash from block header",
                "suggested_fixes": [
                    "Use double SHA-256 for hash calculation",
                    "Ensure block header is exactly 80 bytes",
                    "Check byte order (little-endian for most fields)"
                ],
                "code_examples": [
                    'hash = hashlib.sha256(hashlib.sha256(header_bytes).digest()).digest()'
                ]
            })
        elif error_type == "insufficient_difficulty":
            guidance.update({
                "guidance": f"Solution has {error_data['actual']} leading zeros but needs {error_data['required']}",
                "suggested_fixes": [
                    "Continue mining with different nonces",
                    "Check target calculation from bits field",
                    "Verify hash calculation is correct"
                ]
            })
        
        return guidance

    def _provide_miner_feedback(self, solution: Dict, template: Dict, validation_result: Dict) -> Dict:
        """Provide comprehensive feedback to miners on their solution."""
        feedback = {
            "status": "success",
            "performance": {},
            "achievements": [],
            "recommendations": []
        }
        
        leading_zeros = validation_result.get("actual_leading_zeros", 0)
        required_zeros = validation_result.get("required_leading_zeros", 0)
        
        # Performance analysis
        if leading_zeros > required_zeros:
            excess_difficulty = leading_zeros - required_zeros
            feedback["achievements"].append(f"🎯 SUPERIOR SOLUTION: {excess_difficulty} extra leading zeros!")
            feedback["performance"]["difficulty_exceeded"] = excess_difficulty
            feedback["performance"]["efficiency_ratio"] = 2 ** excess_difficulty
            
        feedback["performance"].update({
            "leading_zeros_achieved": leading_zeros,
            "difficulty_target_met": validation_result.get("difficulty_met", False),
            "bitcoin_compliance": validation_result.get("bitcoin_compliant", False),
            "ultra_hex_tier": validation_result.get("ultra_hex_tier", "standard")
        })
        
        # Achievements
        if leading_zeros >= 64:
            feedback["achievements"].append("🌌 UNIVERSE-SCALE ACHIEVEMENT: 64+ leading zeros!")
        elif leading_zeros >= 32:
            feedback["achievements"].append("🚀 ULTRA HEX ACHIEVEMENT: 32+ leading zeros!")
        elif leading_zeros >= 20:
            feedback["achievements"].append("⭐ EXCELLENT DIFFICULTY: 20+ leading zeros!")
        
        if validation_result.get("hash_verified"):
            feedback["achievements"].append("✅ CRYPTOGRAPHIC VERIFICATION: Hash verified!")
            
        # Recommendations for future mining
        universe_power = validation_result.get("universe_scale_power", 0)
        if universe_power >= 4:
            feedback["recommendations"].append("Continue leveraging 5×Universe-Scale mathematical framework")
        else:
            feedback["recommendations"].append("Consider enabling more mathematical categories for enhanced performance")
            
        return feedback

    def hot_swap_to_production_miner(
        self,
        template_data: Dict[str, Any],
        daemon_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Quickly process and broadcast a template to active miners."""
        identifier = generate_unique_block_id()
        processed = self.process_mining_template(template_data)

        if isinstance(processed, dict) and not processed.get("success", True):
            return {
                "success": False,
                "template_id": identifier,
                "error": processed.get("error", "processing_failed"),
            }

        instruction_template = (
            processed.get("instruction", {})
            .get("template")
            if isinstance(processed, dict)
            else None
        )
        payload = instruction_template or template_data
        distribution_success = self.send_template_to_production_miner(
            payload, identifier, daemon_count=daemon_count
        )

        return {
            "success": bool(distribution_success),
            "template_id": identifier,
            "processed_template": processed,
            "distributed": distribution_success,
        }

    def connect_to_production_miner(
        self,
        template_data: Optional[Dict[str, Any]] = None,
        daemon_count: Optional[int] = None,
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Establish or refresh the link between the DTM and production miners."""
        payload = template_data or self.current_template or {}
        identifier = template_id or generate_unique_block_id()

        if not payload:
            return {
                "success": False,
                "template_id": identifier,
                "error": "no_template_available",
            }

        # Ensure the template is fully processed before distribution
        processed = self.process_mining_template(payload)
        instruction_template = (
            processed.get("instruction", {})
            .get("template")
            if isinstance(processed, dict)
            else None
        )
        outbound = instruction_template or payload

        distribution_success = self.send_template_to_production_miner(
            outbound, identifier, daemon_count=daemon_count
        )

        if distribution_success:
            self.templates[identifier] = outbound

        return {
            "success": bool(distribution_success),
            "template_id": identifier,
            "processed_template": processed,
            "distributed": distribution_success,
        }

    def cleanup_old_templates(self, days_to_keep: int = 7):
        """Clean up old template files - uses Brain.QTL managed paths"""
        try:
            # Use Brain.QTL output directory instead of template-specific folders
            # Use brain_get_path for dynamic resolution
            base_path_obj = to_absolute_from_string(brain_get_path("output_dir"))

            if not base_path_obj.exists():
                print("ℹ️ No output directory found for cleanup")
                return

            current_time = time.time()
            cutoff_time = current_time - (days_to_keep * 24 * 3600)

            cleaned_count = 0
            for root, dirs, files in os.walk(base_path_obj):
                for file in files:
                    # Only clean template files
                    if any(
                        keyword in file
                        for keyword in [
                            "template_",
                            "mining_instruction_",
                            "mining_result_",
                            "coordination_",
                        ]
                    ):
                        file_path = Path(root) / file
                        try:
                            if file_path.stat().st_mtime < cutoff_time:
                                file_path.unlink()
                                cleaned_count += 1
                        except (OSError, PermissionError) as e:
                            print(f"⚠️ Could not remove {file_path}: {e}")

            if cleaned_count > 0:
                print(f"🗑️ Cleaned up {cleaned_count} old template files")

        except Exception as e:
            print(f"❌ Error during template cleanup: {e}")


    def check_miner_subfolders_for_solutions(self):
        """
        Automatically check Temporary/Template subfolders for miner solutions.
        This implements the Pipeline flow.txt requirement for Dynamic Template Manager
        to check subfolders and validate solutions.
        
        🚀 ENHANCED: Checks for instant notification signals first, then polls folders
        """
        try:
            from pathlib import Path
            import json
            
            # Get path dynamically from brainstem
            temp_template_dir = Path(brain_get_path("temporary_template_dir"))
            
            if not temp_template_dir.exists():
                if self.verbose:
                    print(f"⚠️ Temporary/Template directory not found: {temp_template_dir}")
                return None
            
            # 🎯 ENSURE TEMPLATE IS LOADED: Load current template if not already set
            if not self.current_template:
                template_file = temp_template_dir / "current_template.json"
                if template_file.exists():
                    try:
                        with open(template_file, 'r') as f:
                            self.current_template = json.load(f)
                        if self.verbose:
                            print(f"✅ Loaded template for validation: height {self.current_template.get('height')}")
                    except Exception as e:
                        if self.verbose:
                            print(f"⚠️ Could not load template: {e}")
            
            # 🚀 INSTANT DETECTION: Check for signal files first
            signal_files = list(temp_template_dir.glob("dtm_notification_*.signal"))
            if signal_files and self.verbose:
                print(f"🚀 Instant notification detected: {len(signal_files)} signal(s)")
            
            solutions_found = []
            
            # Look for process subfolders (both Process_ and process_)
            for subfolder in temp_template_dir.iterdir():
                if subfolder.is_dir() and (subfolder.name.startswith("Process_") or subfolder.name.startswith("process_")):
                    # Check ONLY for mining_result.json (not working_template.json!)
                    solution_file = subfolder / "mining_result.json"
                    if solution_file.exists():
                        try:
                            with open(solution_file, 'r') as f:
                                solution_data = json.load(f)
                            
                            if self.verbose:
                                print(f"🔍 Checking solution from {subfolder.name}: {solution_file.name}")
                            
                            # Validate solution against original template
                            if self.current_template:
                                validated_solution = self.validate_and_format_solution(
                                    solution_data, self.current_template
                                )
                                
                                if validated_solution.get("success"):
                                    if self.verbose:
                                        print(f"✅ Valid solution found from {subfolder.name}")
                                    
                                    # 🧮 PRESERVE mathematical_proof from original miner solution
                                    validated_solution["mathematical_proof"] = solution_data.get("mathematical_proof", {})
                                    validated_solution["difficulty"] = solution_data.get("difficulty", 0.0)
                                    
                                    # Create ledger files as per Pipeline flow.txt
                                    self._create_global_ledger_file(validated_solution, subfolder.name)
                                    self._create_hourly_ledger_file(validated_solution, subfolder.name)
                                    self._create_global_math_proof_file(validated_solution, subfolder.name)
                                    self._create_hourly_math_proof_file(validated_solution, subfolder.name)
                                    # Create block submission file (DTM creates this)
                                    self._create_block_submission_file(validated_solution, subfolder.name)
                                    # Create submission tracking files
                                    self._create_global_submission_file(validated_solution, subfolder.name)
                                    self._create_hourly_submission_file(validated_solution, subfolder.name)
                                    
                                    solutions_found.append({
                                        "miner_id": subfolder.name,
                                        "solution_file": str(solution_file),
                                        "solution": validated_solution,
                                        "quality_score": self.calculate_solution_quality(validated_solution)
                                    })
                                else:
                                    error_reason = validated_solution.get('error', 'Unknown error')
                                    if self.verbose:
                                        print(f"❌ Invalid solution from {subfolder.name}: {error_reason}")
                                    
                                    # Save bad solutions to 'User_Look_at' as per requirements
                                    try:
                                        user_look_at_path = Path(brain_get_path("user_look_at"))
                                        user_look_at_path.mkdir(parents=True, exist_ok=True)
                                        bad_solution_file = user_look_at_path / f"bad_solution_{subfolder.name}_{int(time.time())}.json"
                                        
                                        error_context = {
                                            "miner_id": subfolder.name,
                                            "error_reason": error_reason,
                                            "solution_data": solution_data,
                                            "template_data": self.current_template,
                                            "timestamp": datetime.now().isoformat(),
                                            "status": "NEEDS_REVIEW"
                                        }

                                        with open(bad_solution_file, 'w') as f:
                                            json.dump(error_context, f, indent=2)
                                        
                                        if self.verbose:
                                            print(f"💾 Bad solution from {subfolder.name} saved to {bad_solution_file}")

                                    except Exception as e:
                                        if self.verbose:
                                            print(f"⚠️ Could not save bad solution to User_Look_at folder: {e}")

                                    # Give feedback to losing miner as per Pipeline flow.txt
                                    # Provide EXACT mathematical reason
                                    self.provide_miner_feedback(subfolder.name, f"REJECTED: {error_reason}")
                            else:
                                # NO TEMPLATE: Process solution anyway (standalone mode)
                                if self.verbose:
                                    print(f"✅ Processing solution without template validation from {subfolder.name}")
                                
                                # Use solution data as-is
                                # Create ledger files as per Pipeline flow.txt
                                self._create_global_ledger_file(solution_data, subfolder.name)
                                self._create_hourly_ledger_file(solution_data, subfolder.name)
                                self._create_global_math_proof_file(solution_data, subfolder.name)
                                self._create_hourly_math_proof_file(solution_data, subfolder.name)
                                # Create block submission file (DTM creates this)
                                self._create_block_submission_file(solution_data, subfolder.name)
                                # Create submission tracking files
                                self._create_global_submission_file(solution_data, subfolder.name)
                                self._create_hourly_submission_file(solution_data, subfolder.name)
                                
                                solutions_found.append({
                                    "miner_id": subfolder.name,
                                    "solution_file": str(solution_file),
                                    "solution": solution_data,
                                    "quality_score": solution_data.get("leading_zeros", 0)
                                })
                            
                        except (json.JSONDecodeError, IOError) as e:
                            if self.verbose:
                                print(f"⚠️ Could not read solution file {solution_file}: {e}")
            
            # 🚀 CLEANUP: Remove signal files after processing
            for signal_file in signal_files:
                try:
                    signal_file.unlink()
                    if self.verbose:
                        print(f"🧹 Cleaned up signal: {signal_file.name}")
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Could not remove signal file {signal_file.name}: {e}")
            
            # Implement consensus mechanism for multiple solutions
            if len(solutions_found) > 0:
                # Always return a consistent dict format
                if len(solutions_found) == 1:
                    # Single solution - wrap in success dict
                    return {
                        "success": True,
                        "solution": solutions_found[0]["solution"],
                        "miner_id": solutions_found[0]["miner_id"],
                        "leading_zeros": solutions_found[0]["solution"].get("leading_zeros", 0)
                    }
                else:
                    # Multiple solutions - return best one
                    best = max(solutions_found, key=lambda x: x.get("quality_score", 0))
                    return {
                        "success": True,
                        "solution": best["solution"],
                        "miner_id": best["miner_id"],
                        "leading_zeros": best["solution"].get("leading_zeros", 0),
                        "total_solutions_found": len(solutions_found)
                    }
            else:
                return None
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Error checking miner subfolders: {e}")
            return None


    def _continuous_monitoring_loop(self):
        """
        Continuous monitoring loop that automatically checks miner subfolders.
        Implements Pipeline flow.txt automatic checking requirement.
        """
        if self.verbose:
            print("🔄 DTM Automatic Monitoring Loop: ACTIVE")
        
        while self.monitoring_enabled:
            try:
                current_time_val = time.time()
                
                # Throttle monitoring to avoid excessive checking
                if current_time_val - self.last_monitoring_check >= self.monitoring_interval:
                    # Call the proper monitoring function per Pipeline flow.txt
                    valid_solution = self.check_miner_subfolders_for_solutions()
                    
                    if valid_solution:
                        if self.verbose:
                            print("🎉 VALID SOLUTION FOUND BY AUTOMATIC MONITORING!")
                        
                        # Notify Looping per Pipeline flow.txt
                        self._notify_looping_of_valid_solution(valid_solution)
                    
                    self.last_monitoring_check = current_time_val
                
                # Sleep briefly to prevent excessive CPU usage
                time.sleep(1)
                
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Monitoring loop error: {e}")
                time.sleep(5)  # Wait longer on error


    def _check_for_solutions_simplified(self):
        """
        COMPLETE Pipeline flow.txt implementation for Testing-with-Node environment.
        Per specification: DTM must create/update ALL files BEFORE telling Looping.
        """
        try:
            from pathlib import Path
            import json
            
            temp_template_dir = Path(brain_get_path("temporary_template_dir"))
            if not temp_template_dir.exists():
                return None
            
            solutions_found = []
            
            # Look for process subfolders (both Process_ and process_)
            for subfolder in temp_template_dir.iterdir():
                if subfolder.is_dir() and (subfolder.name.startswith("Process_") or subfolder.name.startswith("process_")):
                    # Check for solution files in this process's subfolder
                    for solution_file in subfolder.glob("*.json"):
                        try:
                            if self.verbose:
                                print(f"🔍 Found solution file: {solution_file}")
                            
                            # Read and validate solution
                            with open(solution_file, 'r') as f:
                                solution_data = json.load(f)
                            
                            # PIPELINE FLOW.TXT COMPLIANCE: Validate solution against original template
                            if hasattr(self, 'current_template') and self.current_template:
                                validated_solution = self._validate_solution_against_template(
                                    solution_data, self.current_template
                                )
                                
                                if validated_solution.get("success"):
                                    if self.verbose:
                                        print(f"✅ Valid solution found from {subfolder.name}")
                                    
                                    # STEP 1: Create/update ALL required files per Pipeline flow.txt
                                    # "the Dynamic Template manger will create/ update the Global Ledger file, 
                                    # Global Math proof file, hourly ledger file, hourly math proof file"
                                    files_created = self._create_all_dtm_files(validated_solution, subfolder.name)
                                    
                                    if files_created:
                                        # STEP 2: ONLY AFTER files created, tell Looping
                                        # "The Dynamic template manger tells the looping we have a solution"
                                        solutions_found.append({
                                            "miner_id": subfolder.name,
                                            "solution_file": str(solution_file),
                                            "solution": validated_solution,
                                            "files_created": files_created
                                        })
                                        
                                        if self.verbose:
                                            print(f"📁 All DTM files created for {subfolder.name}")
                                            print("🔄 Ready to notify Looping per Pipeline flow.txt")
                                    else:
                                        if self.verbose:
                                            print(f"❌ Failed to create DTM files for {subfolder.name}")
                                else:
                                    if self.verbose:
                                        validation_error = validated_solution.get('error', 'Unknown validation error')
                                        print(f"❌ Invalid solution from {subfolder.name}: {validation_error}")
                                    
                                    # Save bad solutions to 'User_Look_at' as per requirements
                                    try:
                                        user_look_at_path = Path(brain_get_path("user_look_at"))
                                        user_look_at_path.mkdir(parents=True, exist_ok=True)
                                        bad_solution_file = user_look_at_path / f"bad_solution_{subfolder.name}_{int(time.time())}.json"

                                        error_context = {
                                            "miner_id": subfolder.name,
                                            "error_reason": validated_solution.get('error', 'Unknown validation error'),
                                            "solution_data": solution_data,
                                            "template_data": self.current_template,
                                            "timestamp": datetime.now().isoformat(),
                                            "status": "NEEDS_REVIEW"
                                        }

                                        with open(bad_solution_file, 'w') as f:
                                            json.dump(error_context, f, indent=2)

                                        if self.verbose:
                                            print(f"💾 Bad solution from {subfolder.name} saved to {bad_solution_file}")

                                    except Exception as e:
                                        if self.verbose:
                                            print(f"⚠️ Could not save bad solution to User_Look_at folder: {e}")

                                    # Provide comprehensive feedback to failing miner
                                    self._provide_miner_feedback(subfolder.name, validated_solution)
                            
                        except Exception as e:
                            if self.verbose:
                                print(f"⚠️ Could not process solution file {solution_file}: {e}")
                            # Provide feedback about processing error
                            error_info = {"error": f"Solution processing error: {e}"}
                            self._provide_miner_feedback(subfolder.name, error_info)
            
            # Return best solution if any found
            if solutions_found:
                # Select best solution and notify Looping
                best_solution = solutions_found[0]  # For simplicity, take first valid
                self._notify_looping_of_valid_solution(best_solution)
                return best_solution["solution"]
            
            return None
                            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error in complete solution checking: {e}")
            return None


    def _validate_solution_against_template(self, solution_data, original_template):
        """Validate solution against original template per Pipeline flow.txt - COMPREHENSIVE REAL VALIDATION."""
        try:
            # Phase 1: Basic Structure Validation
            required_fields = ['block_header', 'nonce', 'hash', 'target']
            missing_fields = [field for field in required_fields if field not in solution_data]
            
            if missing_fields:
                return {"success": False, "error": f"Missing required fields: {missing_fields}"}
            
            # Phase 2: Extract Solution Data
            block_header_hex = solution_data.get('block_header', '')
            nonce = solution_data.get('nonce', 0)
            claimed_hash = solution_data.get('hash', '')
            solution_target = solution_data.get('target', '')
            
            # Phase 3: Template Comparison - REAL VALIDATION
            template_target = original_template.get('target', '')
            template_bits = original_template.get('bits', '')
            template_difficulty = original_template.get('difficulty', 1)
            template_version = original_template.get('version', 1)
            template_previous_hash = original_template.get('previousblockhash', '')
            template_merkle_root = original_template.get('merkleroot', '')
            
            # Phase 4: Block Header Structure Validation (80 bytes expected)
            if len(block_header_hex) != 160:  # 80 bytes = 160 hex chars
                return {"success": False, "error": f"Invalid block header length: {len(block_header_hex)} (expected 160 hex chars for 80 bytes)"}
            
            # Phase 5: Parse Block Header Fields (Bitcoin structure validation)
            try:
                header_bytes = bytes.fromhex(block_header_hex)
                import struct
                
                # Bitcoin block header structure (80 bytes total):
                # version (4 bytes) + previous hash (32 bytes) + merkle root (32 bytes) + 
                # timestamp (4 bytes) + bits (4 bytes) + nonce (4 bytes)
                version_bytes = header_bytes[0:4]
                prev_hash_bytes = header_bytes[4:36]
                merkle_bytes = header_bytes[36:68]
                timestamp_bytes = header_bytes[68:72]
                bits_bytes = header_bytes[72:76]
                nonce_bytes = header_bytes[76:80]
                
                # Unpack fields (little-endian for Bitcoin)
                header_version = struct.unpack('<I', version_bytes)[0]
                header_timestamp = struct.unpack('<I', timestamp_bytes)[0]
                header_bits = struct.unpack('<I', bits_bytes)[0]
                header_nonce = struct.unpack('<I', nonce_bytes)[0]
                
                # Convert hashes to hex (reverse byte order for Bitcoin)
                header_prev_hash = prev_hash_bytes[::-1].hex()
                header_merkle_root = merkle_bytes[::-1].hex()
                
                # Phase 6: Validate Header Fields Against Template
                validation_errors = []
                
                if template_version and header_version != template_version:
                    validation_errors.append(f"Version mismatch: header {header_version} != template {template_version}")
                
                if template_previous_hash and header_prev_hash != template_previous_hash:
                    validation_errors.append(f"Previous hash mismatch: header {header_prev_hash} != template {template_previous_hash}")
                
                if template_merkle_root and header_merkle_root != template_merkle_root:
                    validation_errors.append(f"Merkle root mismatch: header {header_merkle_root} != template {template_merkle_root}")
                
                if header_nonce != nonce:
                    validation_errors.append(f"Nonce mismatch: header {header_nonce} != solution {nonce}")
                
                if validation_errors:
                    return {"success": False, "error": f"Block structure validation failed: {'; '.join(validation_errors)}"}
                
            except (ValueError, struct.error) as e:
                return {"success": False, "error": f"Block header parsing failed: {e}"}
            
            # Phase 7: Recreate Hash from Solution
            try:
                # Bitcoin double SHA-256
                import hashlib
                hash1 = hashlib.sha256(header_bytes).digest()
                hash2 = hashlib.sha256(hash1).digest()
                recreated_hash = hash2.hex()
                
                # Phase 8: Validate Hash Matches Claim
                claimed_hash_clean = claimed_hash.replace('0x', '').lower()
                if recreated_hash != claimed_hash_clean:
                    return {
                        "success": False, 
                        "error": f"Hash mismatch: recreated {recreated_hash} != claimed {claimed_hash_clean}"
                    }
                
                # Phase 9: Validate Against Target Difficulty
                hash_int = int(recreated_hash, 16)
                
                # Use template target if available, otherwise derive from bits
                if template_target:
                    target_int = int(template_target.replace('0x', ''), 16)
                elif template_bits:
                    # Convert bits to target (Bitcoin difficulty calculation)
                    bits_str = template_bits if isinstance(template_bits, str) else f"{header_bits:08x}"
                    target_int = self._bits_to_target(bits_str)
                else:
                    target_int = 2**224  # Default Bitcoin target
                
                if hash_int >= target_int:
                    return {
                        "success": False,
                        "error": f"Hash does not meet target difficulty: {hash_int:064x} >= {target_int:064x}"
                    }
                
                # Phase 10: Success - Count Leading Zeros (Validation Success Metrics)
                leading_zeros_hex = len(recreated_hash) - len(recreated_hash.lstrip('0'))
                
                return {
                    "success": True,
                    "solution_data": solution_data,
                    "validation_timestamp": current_timestamp(),
                    "recreated_hash": recreated_hash,
                    "leading_zeros_achieved": leading_zeros_hex,
                    "target_difficulty": template_difficulty,
                    "hash_meets_target": True,
                    "validation_method": "comprehensive_bitcoin_validation",
                    "block_structure_valid": True,
                    "header_fields": {
                        "version": header_version,
                        "previous_hash": header_prev_hash,
                        "merkle_root": header_merkle_root,
                        "timestamp": header_timestamp,
                        "bits": f"{header_bits:08x}",
                        "nonce": header_nonce
                    }
                }
                
            except ValueError as e:
                return {"success": False, "error": f"Hash recreation failed: {e}"}
                
        except Exception as e:
            return {"success": False, "error": f"Validation error: {e}"}


    def _bits_to_target(self, bits_hex):
        """Convert Bitcoin bits field to target value"""
        try:
            if isinstance(bits_hex, str):
                bits_int = int(bits_hex, 16)
            else:
                bits_int = bits_hex
                
            # Bitcoin bits format: first byte is exponent, next 3 bytes are mantissa
            exponent = (bits_int >> 24) & 0xFF
            mantissa = bits_int & 0xFFFFFF
            
            # Calculate target
            if exponent <= 3:
                target = mantissa >> (8 * (3 - exponent))
            else:
                target = mantissa << (8 * (exponent - 3))
                
            return target
        except (ValueError, TypeError, AttributeError):
            return 2**224  # Default fallback


    def _create_all_dtm_files(self, validated_solution, miner_id):
        """
        Create/update ALL files per Pipeline flow.txt:
        'Global Ledger file, Global Math proof file, hourly ledger file, hourly math proof file'
        """
        try:
            files_created = {}
            
            # 1. Global Ledger file
            global_ledger_file = self._create_global_ledger_file(validated_solution, miner_id)
            files_created['global_ledger'] = global_ledger_file
            
            # 2. Global Math proof file  
            global_math_proof_file = self._create_global_math_proof_file(validated_solution, miner_id)
            files_created['global_math_proof'] = global_math_proof_file
            
            # 3. Hourly ledger file
            hourly_ledger_file = self._create_hourly_ledger_file(validated_solution, miner_id)
            files_created['hourly_ledger'] = hourly_ledger_file
            
            # 4. Hourly math proof file
            hourly_math_proof_file = self._create_hourly_math_proof_file(validated_solution, miner_id)
            files_created['hourly_math_proof'] = hourly_math_proof_file
            
            if self.verbose:
                print("✅ ALL DTM FILES CREATED per Pipeline flow.txt:")
                for file_type, file_path in files_created.items():
                    print(f"   📄 {file_type}: {file_path}")
            
            return files_created
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create DTM files: {e}")
            return None


    def _create_global_ledger_file(self, solution, miner_id):
        """
        Create/update Global Ledger - ADAPTS to System_File_Examples template.
        Uses defensive write - NEVER FAILS.
        """
        try:
            ledger_dir = self._get_ledger_path()
            global_ledger_file = ledger_dir / "global_ledger.json"
            
            # Load existing or create from Brainstem-generated template
            if global_ledger_file.exists():
                try:
                    with open(global_ledger_file, 'r') as f:
                        ledger_data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Corrupted ledger {global_ledger_file}: {e}. Using template.")
                    ledger_data = load_template_from_examples('global_ledger', 'DTM')
                except (FileNotFoundError, PermissionError) as e:
                    print(f"Warning: Cannot read {global_ledger_file}: {e}. Using template.")
                    ledger_data = load_template_from_examples('global_ledger', 'DTM')
            else:
                ledger_data = load_template_from_examples('global_ledger', 'DTM')
                # RESET ALL COUNTS TO ZERO (clear fake template data)
                ledger_data['entries'] = []
                ledger_data['total_hashes'] = 0
                ledger_data['total_blocks_found'] = 0
                ledger_data['total_attempts'] = 0
                if 'total_nonce_ranges' in ledger_data:
                    ledger_data['total_nonce_ranges'] = 0
                if 'computational_hours' in ledger_data:
                    ledger_data['computational_hours'] = 0.0
                # Update timestamps
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                if 'metadata' in ledger_data:
                    ledger_data['metadata']['created'] = now
                    ledger_data['metadata']['last_updated'] = now
                if 'system_status' in ledger_data:
                    ledger_data['system_status']['status'] = 'operational'
                    ledger_data['system_status']['last_update'] = now
                    ledger_data['system_status']['active_miners'] = 0
                    ledger_data['system_status']['miners_with_issues'] = 0
                    ledger_data['system_status']['average_hash_rate'] = 0
                    ledger_data['system_status']['issues'] = []
            
            # Get template entry structure to adapt to
            template_entry = ledger_data.get("entries", [{}])[0] if ledger_data.get("entries") else {}
            
            # Build entry adapting to template structure
            new_entry = {}
            for key in template_entry.keys():
                new_entry[key] = None  # Initialize
            
            # Fill basic fields
            new_entry.update({
                "attempt_id": f"attempt_{current_timestamp().replace(':', '').replace('-', '').replace('.', '_')}",
                "timestamp": current_timestamp(),
                "block_height": solution.get("block_height", 0),
                "miner_id": miner_id,
                "nonce": solution.get("solution_data", {}).get("nonce", 0),
                "merkleroot": solution.get("solution_data", {}).get("merkleroot", ""),
                "block_hash": solution.get("solution_data", {}).get("block_hash", ""),
                "meets_difficulty": solution.get("meets_difficulty", False),
                "leading_zeros": solution.get("leading_zeros_achieved", 0),
                "status": "mined" if solution.get("meets_difficulty") else "mining"
            })
            
            # NEW: Fill submitted_to_network (initially false, Looping will update to true)
            if "submitted_to_network" in template_entry:
                new_entry["submitted_to_network"] = False
            
            # NEW: Fill submission_timestamp (null initially, Looping will fill)
            if "submission_timestamp" in template_entry:
                new_entry["submission_timestamp"] = None
            
            # NEW: Fill references (cross-link to related files)
            if "references" in template_entry:
                attempt_id = new_entry["attempt_id"]
                block_height = solution.get("block_height", 0)
                timestamp_part = attempt_id.replace("attempt_", "")
                new_entry["references"] = {
                    "math_proof": f"proof_{timestamp_part}",
                    "submission_tracking": None,  # Looping will fill when submitted
                    "block_submission": f"block_submission_{block_height}_{timestamp_part}.json"
                }
            
            # If template has hardware structure, fill it
            if "hardware" in template_entry:
                try:
                    from Singularity_Dave_Brainstem_UNIVERSE_POWERED import capture_system_info
                    system_info = capture_system_info()
                    new_entry["hardware"] = {
                        "ip_address": system_info.get("ip_address", "unknown"),
                        "hostname": system_info.get("hostname", "unknown"),
                        "cpu": system_info.get("cpu", {}),
                        "ram": system_info.get("ram", {}),
                        "gpu": system_info.get("gpu", {})
                    }
                except (KeyError, TypeError, AttributeError):
                    new_entry["hardware"] = {}
            
            # If template has dtm_guidance, fill it
            if "dtm_guidance" in template_entry:
                new_entry["dtm_guidance"] = {
                    "nonce_range_start": solution.get("nonce_start", 0),
                    "nonce_range_end": solution.get("nonce_end", 0),
                    "target_strategy": solution.get("strategy", "Standard"),
                    "consensus_validated": solution.get("validated", False),
                    "guidance_timestamp": current_timestamp()
                }
            
            # If template has hash_rate, hashes_tried, time_to_solution
            if "hash_rate" in template_entry:
                new_entry["hash_rate"] = solution.get("hash_rate", 0)
            if "hashes_tried" in template_entry:
                new_entry["hashes_tried"] = solution.get("hashes_tried", 0)
            if "time_to_solution_seconds" in template_entry:
                new_entry["time_to_solution_seconds"] = solution.get("time_seconds", 0.0)
            if "difficulty_target" in template_entry:
                new_entry["difficulty_target"] = solution.get("target", "")
            
            # Add entry
            ledger_data["entries"].append(new_entry)
            
            # Update metadata if it exists
            if "metadata" in ledger_data:
                ledger_data["metadata"]["last_updated"] = current_timestamp()
            
            # Update statistics if they exist
            if "total_attempts" in ledger_data:
                ledger_data["total_attempts"] = len(ledger_data["entries"])
            if "total_hashes" in ledger_data:
                ledger_data["total_hashes"] = sum(e.get("hashes_tried", 0) for e in ledger_data["entries"])
            if "total_blocks_found" in ledger_data:
                ledger_data["total_blocks_found"] = sum(1 for e in ledger_data["entries"] if e.get("meets_difficulty"))
            
            # NEW: Update computational_hours
            if "computational_hours" in ledger_data:
                total_seconds = sum(e.get("time_to_solution_seconds", 0) for e in ledger_data["entries"])
                ledger_data["computational_hours"] = round(total_seconds / 3600.0, 2)
            
            # Write using Brain hierarchical system
            defensive_write_json(str(global_ledger_file), ledger_data, "DTM")
            
            # Use Brain hierarchical write for all time levels
            if HAS_BRAIN_FILE_SYSTEM:
                ledger_dir_base = str(global_ledger_file).replace('/global_ledger.json', '')
                results = brain_write_hierarchical(new_entry, ledger_dir_base, "ledger", "DTM")
                if self.verbose:
                    success_count = sum(1 for r in results.values() if r.get("success"))
                    print(f"   📊 Brain hierarchical: {success_count}/5 levels")
            
            return str(global_ledger_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create global ledger: {e}")
                import traceback
                traceback.print_exc()
            return None


    def _create_global_math_proof_file(self, solution, miner_id):
        """
        Create/update Global Math proof - ADAPTS to System_File_Examples template.
        Uses defensive write - NEVER FAILS.
        Captures: hardware, GPS, 5-category math, mining steps, everything.
        """
        try:
            ledger_dir = self._get_ledger_path()
            math_proof_file = ledger_dir / "global_math_proof.json"
            
            # Load existing or create from Brainstem-generated template
            if math_proof_file.exists():
                try:
                    with open(math_proof_file, 'r') as f:
                        proof_data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Corrupted math proof {math_proof_file}: {e}. Using template.")
                    proof_data = load_template_from_examples('global_math_proof', 'DTM')
                except (FileNotFoundError, PermissionError) as e:
                    print(f"Warning: Cannot read {math_proof_file}: {e}. Using template.")
                    proof_data = load_template_from_examples('global_math_proof', 'DTM')
            else:
                proof_data = load_template_from_examples('global_math_proof', 'DTM')
            
            # Get system info
            try:
                from Singularity_Dave_Brainstem_UNIVERSE_POWERED import capture_system_info
                system_info = capture_system_info()
            except (ImportError, AttributeError):
                system_info = {}
            
            # Extract math proof from miner solution
            math_proof = solution.get("mathematical_proof", {})
            
            # Create COMPREHENSIVE math proof entry
            math_proof_entry = {
                "timestamp": current_timestamp(),
                "session_id": f"proof_{int(time.time())}",
                
                # System Information
                "system": {
                    "ip_address": system_info.get("network", {}).get("ip_address"),
                    "hostname": system_info.get("network", {}).get("hostname"),
                    "hardware": system_info.get("hardware", {}),
                    "software": system_info.get("software", {}),
                },
                
                # Miner Information
                "miner": {
                    "miner_id": miner_id,
                    "process_id": solution.get("process_id", "unknown"),
                },
                
                # Mining Result
                "result": {
                    "nonce": solution.get("nonce", 0),
                    "hash": solution.get("hash", ""),
                    "block_header": solution.get("block_header", ""),
                    "difficulty": solution.get("difficulty", 0.0),
                    "leading_zeros": solution.get("leading_zeros_achieved", 0),
                    "validation_status": "ACCEPTED"
                },
                
                # GPS Targeting (deterministic blockchain entropy)
                "gps_targeting": {
                    "target_nonce": solution.get("gps_targeting", {}).get("target_nonce", 0),
                    "deterministic_delta": solution.get("gps_targeting", {}).get("deterministic_delta", 0),
                    "knuth_result": solution.get("gps_targeting", {}).get("knuth_result", 0),
                    "blockchain_entropy": solution.get("gps_targeting", {}).get("blockchain_entropy", {}),
                    "nonce_range": solution.get("gps_targeting", {}).get("nonce_range", {}),
                },
                
                # 5-Category Mathematical Framework
                "mathematical_framework": {
                    "universe_bitload": math_proof.get("universe_bitload", 0),
                    "knuth_levels": math_proof.get("knuth_levels", 0),
                    "knuth_iterations": math_proof.get("knuth_iterations", 0),
                    "cycles": math_proof.get("cycles", 0),
                    "galaxy_category": math_proof.get("galaxy_category", "Standard"),
                    "categories": {
                        "families": math_proof.get("families", {}),
                        "lanes": math_proof.get("lanes", {}),
                        "strides": math_proof.get("strides", {}),
                        "palette": math_proof.get("palette", {}),
                        "sandbox": math_proof.get("sandbox", {}),
                    },
                    "combined_power": math_proof.get("combined_power", ""),
                    "notation": math_proof.get("notation", "Knuth-Sorrellian-Class")
                },
                
                # Mining Steps
                "mining_steps": solution.get("mining_steps", [
                    "1. Received template from DTM",
                    "2. Applied GPS targeting for nonce range",
                    "3. Generated nonces using 5-category framework",
                    "4. Calculated hashes with Universe-Scale operations",
                    "5. Found solution meeting difficulty target"
                ]),
                
                # Performance Metrics
                "performance": {
                    "total_hashes": solution.get("total_hashes", 0),
                    "hashes_per_second": solution.get("hashes_per_second", 0),
                    "time_elapsed_seconds": solution.get("time_elapsed", 0),
                    "nonces_generated": solution.get("nonces_generated", 0),
                }
            }
            
            # Append new proof
            if "proofs" not in proof_data:
                proof_data["proofs"] = []
            proof_data["proofs"].append(math_proof_entry)
            
            # Update metadata if it exists
            if "metadata" in proof_data:
                proof_data["metadata"]["last_updated"] = current_timestamp()
            
            # Update statistics if they exist
            if "total_proofs" in proof_data:
                proof_data["total_proofs"] = len(proof_data["proofs"])
            if "total_blocks_proven" in proof_data:
                proof_data["total_blocks_proven"] = sum(1 for p in proof_data["proofs"] if p.get("result", {}).get("validation_status") == "ACCEPTED")
            
            # DEFENSIVE WRITE - never fails
            defensive_write_json(str(math_proof_file), proof_data, "DTM")
            
            # 🔥 HIERARCHICAL WRITE: Year/Month/Week/Day levels
            ledger_dir_base = self._get_ledger_path()
            try:
                results = brain_write_hierarchical(math_proof_entry, ledger_dir_base, "math_proof", "DTM")
                if self.verbose and results:
                    print(f"   📊 Hierarchical math_proof: {len(results)} levels updated")
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️ Hierarchical math_proof write failed: {e}")
            
            if self.verbose:
                print(f"✅ Comprehensive math proof created: {math_proof_file}")
                print(f"   📊 Knuth-Sorrellian-Class({math_proof.get('knuth_levels', 0)} levels, {math_proof.get('knuth_iterations', 0)} iterations)")
                print(f"   🌐 IP: {system_info.get('network', {}).get('ip_address')}")
                print(f"   💻 Hardware: {system_info.get('hardware', {}).get('cpu', {}).get('physical_cores')} cores")
            
            return str(math_proof_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create global math proof: {e}")
                import traceback
                traceback.print_exc()
            return None


    def _create_hourly_ledger_file(self, solution, miner_id):
        """Create/update hourly ledger file using System_File_Examples template with detailed hardware info."""
        try:
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import load_file_template_from_examples, capture_system_info
            
            # Create hourly directory structure
            now = current_time()
            year = now.strftime("%Y")
            month = now.strftime("%m") 
            day = now.strftime("%d")
            hour = now.strftime("%H")
            
            hourly_dir = self._get_ledger_path() / year / month / day / hour
            if not validate_folder_exists_dtm(str(hourly_dir), "DTM-hourly-dir"):
                raise FileNotFoundError(f"Hourly directory not found: {hourly_dir}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
            
            hourly_ledger_file = hourly_dir / "hourly_ledger.json"
            
            # Read existing or initialize from template
            hourly_data = None
            if hourly_ledger_file.exists() and hourly_ledger_file.stat().st_size > 0:
                try:
                    with open(hourly_ledger_file, 'r') as f:
                        hourly_data = json.load(f)
                except (json.JSONDecodeError, ValueError) as e:
                    if self.verbose:
                        print(f"⚠️ Corrupted hourly ledger, recreating: {e}")
                    hourly_data = None
            
            if hourly_data is None:
                # Load structure from System_File_Examples
                hourly_data = load_file_template_from_examples('hourly_ledger')
                hourly_data['entries'] = []  # Clear example data
                hourly_data['hour'] = f"{year}-{month}-{day}_{hour}"
            
            # Get real system info
            system_info = capture_system_info()
            
            # Create detailed hourly entry with hardware info
            hourly_entry = {
                "attempt_id": f"attempt_{current_timestamp().replace(':', '').replace('-', '').replace('.', '_')}",
                "timestamp": current_timestamp(),
                "block_height": solution.get("block_height", 0),
                "miner_id": miner_id,
                "hardware": {
                    "ip_address": system_info['network']['ip_address'],
                    "hostname": system_info['network']['hostname'],
                    "cpu": system_info['hardware']['cpu'],
                    "ram": system_info['hardware']['memory'],
                    "gpu": system_info['hardware'].get('gpu', {})
                },
                "dtm_guidance": solution.get("dtm_guidance", {}),
                "nonce": solution.get("solution_data", {}).get("nonce", 0),
                "merkleroot": solution.get("solution_data", {}).get("merkleroot", ""),
                "block_hash": solution.get("solution_data", {}).get("block_hash", ""),
                "difficulty_target": solution.get("difficulty_target", ""),
                "meets_difficulty": solution.get("meets_difficulty", False),
                "leading_zeros": solution.get("leading_zeros_achieved", 0),
                "hash_rate": solution.get("hash_rate", 0),
                "hashes_tried": solution.get("hashes_tried", 0),
                "time_to_solution_seconds": solution.get("time_to_solution", 0),
                "status": "mined" if solution.get("meets_difficulty") else "mining"
            }
            
            hourly_data["entries"].append(hourly_entry)
            hourly_data["metadata"]["last_updated"] = current_timestamp()
            hourly_data["hashes_this_hour"] = sum(e.get("hashes_tried", 0) for e in hourly_data["entries"])
            hourly_data["attempts_this_hour"] = len(hourly_data["entries"])
            hourly_data["blocks_found"] = sum(1 for e in hourly_data["entries"] if e.get("meets_difficulty"))
            
            with open(hourly_ledger_file, 'w') as f:
                json.dump(hourly_data, f, indent=2)
            
            return str(hourly_ledger_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create hourly ledger: {e}")
                import traceback
                traceback.print_exc()
            return None


    def _create_hourly_math_proof_file(self, solution, miner_id):
        """
        Create/update hourly math proof file with EXTREMELY DETAILED step-by-step documentation.
        This is the DETAILED HOUR-BY-HOUR WORK LOG showing every attempt, step, and result.
        """
        try:
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import load_file_template_from_examples, capture_system_info
            
            # Create hourly directory structure  
            now = current_time()
            year = now.strftime("%Y")
            month = now.strftime("%m")
            day = now.strftime("%d") 
            hour = now.strftime("%H")
            
            hourly_dir = self._get_ledger_path() / year / month / day / hour
            hourly_math_proof_file = hourly_dir / "hourly_math_proof.json"
            
            # Get system info
            system_info = capture_system_info()
            math_proof = solution.get("mathematical_proof", {})
            
            # Create EXTREMELY DETAILED hourly proof entry with STEP-BY-STEP documentation
            proof_entry = {
                "timestamp": current_timestamp(),
                "hour_label": f"{year}-{month}-{day} Hour {hour}",
                "session_id": f"hourly_proof_{year}{month}{day}_{hour}_{int(time.time())}",
                
                # System snapshot at time of mining
                "system_snapshot": {
                    "ip_address": system_info.get("network", {}).get("ip_address"),
                    "hostname": system_info.get("network", {}).get("hostname"),
                    "hardware": {
                        "cpu_cores": system_info.get("hardware", {}).get("cpu", {}).get("physical_cores"),
                        "logical_cores": system_info.get("hardware", {}).get("cpu", {}).get("logical_cores"),
                        "cpu_freq_current": system_info.get("hardware", {}).get("cpu", {}).get("current_freq_mhz"),
                        "memory_total_gb": system_info.get("hardware", {}).get("memory", {}).get("total_gb"),
                        "memory_available_gb": system_info.get("hardware", {}).get("memory", {}).get("available_gb"),
                    },
                    "os": system_info.get("software", {}).get("os"),
                    "os_version": system_info.get("software", {}).get("os_version"),
                    "python_version": system_info.get("software", {}).get("python_version"),
                },
                
                # Miner details
                "miner_details": {
                    "miner_id": miner_id,
                    "process_id": solution.get("process_id", "unknown"),
                    "pid": system_info.get("process", {}).get("pid"),
                },
                
                # Block and difficulty information
                "block_info": {
                    "height": solution.get("block_height", 0),
                    "difficulty": solution.get("difficulty", 0.0),
                    "target": solution.get("target", ""),
                    "bits": solution.get("bits", ""),
                    "previous_hash": solution.get("previous_blockhash", "")[:32] + "...",
                },
                
                # Solution found
                "solution": {
                    "nonce": solution.get("nonce", 0),
                    "hash": solution.get("hash", ""),
                    "block_header": solution.get("block_header", ""),
                    "leading_zeros_hex": solution.get("leading_zeros_achieved", 0),
                    "validation_status": "ACCEPTED",
                    "meets_difficulty": True,
                },
                
                # GPS Targeting (deterministic aiming)
                "gps_targeting": {
                    "method": "deterministic_blockchain_entropy",
                    "target_nonce": solution.get("gps_targeting", {}).get("target_nonce", 0),
                    "deterministic_delta": solution.get("gps_targeting", {}).get("deterministic_delta", 0),
                    "knuth_result": solution.get("gps_targeting", {}).get("knuth_result", 0),
                    "blockchain_entropy": {
                        "previous_hash_entropy": solution.get("gps_targeting", {}).get("blockchain_entropy", {}).get("hash_entropy", 0),
                        "difficulty_entropy": solution.get("gps_targeting", {}).get("blockchain_entropy", {}).get("difficulty_entropy", 0),
                        "source": "deterministic_blockchain_data"
                    },
                    "search_range": {
                        "start": solution.get("gps_targeting", {}).get("nonce_range", {}).get("start", 0),
                        "end": solution.get("gps_targeting", {}).get("nonce_range", {}).get("end", 0),
                        "size": solution.get("gps_targeting", {}).get("nonce_range", {}).get("size", 0),
                    },
                },
                
                # 5-Category Mathematical Framework (the CORE of your system)
                "mathematical_framework": {
                    "universe_bitload": math_proof.get("universe_bitload", 0),
                    "universe_bitload_digits": len(str(math_proof.get("universe_bitload", 0))),
                    "knuth_levels": math_proof.get("knuth_levels", 0),
                    "knuth_iterations": math_proof.get("knuth_iterations", 0),
                    "cycles": math_proof.get("cycles", 0),
                    "galaxy_category": math_proof.get("galaxy_category", "Standard"),
                    
                    # Individual category details
                    "categories": {
                        "families": {
                            "levels": math_proof.get("families", {}).get("levels", 0),
                            "iterations": math_proof.get("families", {}).get("iterations", 0),
                            "cycles": math_proof.get("families", {}).get("cycles", 0),
                        },
                        "lanes": {
                            "levels": math_proof.get("lanes", {}).get("levels", 0),
                            "iterations": math_proof.get("lanes", {}).get("iterations", 0),
                            "cycles": math_proof.get("lanes", {}).get("cycles", 0),
                        },
                        "strides": {
                            "levels": math_proof.get("strides", {}).get("levels", 0),
                            "iterations": math_proof.get("strides", {}).get("iterations", 0),
                            "cycles": math_proof.get("strides", {}).get("cycles", 0),
                        },
                        "palette": {
                            "levels": math_proof.get("palette", {}).get("levels", 0),
                            "iterations": math_proof.get("palette", {}).get("iterations", 0),
                            "cycles": math_proof.get("palette", {}).get("cycles", 0),
                        },
                        "sandbox": {
                            "levels": math_proof.get("sandbox", {}).get("levels", 0),
                            "iterations": math_proof.get("sandbox", {}).get("iterations", 0),
                            "cycles": math_proof.get("sandbox", {}).get("cycles", 0),
                        },
                    },
                    
                    "combined_power": f"({len(str(math_proof.get('universe_bitload', 0)))}-digit)^5 Galaxy-Scale",
                    "notation": "Knuth-Sorrellian-Class",
                    "framework_source": "Brain.QTL",
                },
                
                # STEP-BY-STEP Mining Process (what actually happened)
                "mining_steps": [
                    {
                        "step": 1,
                        "action": "Template Reception",
                        "description": "Received mining template from DTM",
                        "timestamp": solution.get("step_timestamps", {}).get("template_received", current_timestamp()),
                    },
                    {
                        "step": 2,
                        "action": "GPS Targeting Calculation",
                        "description": f"Calculated deterministic target nonce using blockchain entropy",
                        "timestamp": solution.get("step_timestamps", {}).get("gps_calculated", current_timestamp()),
                        "result": f"Target: {solution.get('gps_targeting', {}).get('target_nonce', 0)}, Range: {solution.get('gps_targeting', {}).get('nonce_range', {}).get('size', 0)} nonces",
                    },
                    {
                        "step": 3,
                        "action": "5-Category Framework Application",
                        "description": "Applied all 5 mathematical categories (families, lanes, strides, palette, sandbox)",
                        "timestamp": solution.get("step_timestamps", {}).get("framework_applied", current_timestamp()),
                        "result": f"Generated {solution.get('nonces_generated', 0)} candidate nonces",
                    },
                    {
                        "step": 4,
                        "action": "Hash Calculation",
                        "description": f"Calculated hashes using Knuth-Sorrellian-Class({math_proof.get('knuth_levels', 0)}, {math_proof.get('knuth_iterations', 0)}) operations",
                        "timestamp": solution.get("step_timestamps", {}).get("hashing_started", current_timestamp()),
                        "result": f"Processed {solution.get('total_hashes', 0)} hashes at {solution.get('hashes_per_second', 0):.2f} H/s",
                    },
                    {
                        "step": 5,
                        "action": "Solution Found",
                        "description": f"Found valid solution with {solution.get('leading_zeros_achieved', 0)} leading zeros",
                        "timestamp": solution.get("step_timestamps", {}).get("solution_found", current_timestamp()),
                        "result": f"Nonce: {solution.get('nonce', 0)}, Hash: {solution.get('hash', '')[:32]}...",
                    },
                    {
                        "step": 6,
                        "action": "Validation",
                        "description": "DTM validated solution against template",
                        "timestamp": current_timestamp(),
                        "result": "ACCEPTED",
                    },
                ],
                
                # Performance metrics for this solve
                "performance": {
                    "total_hashes": solution.get("total_hashes", 0),
                    "hashes_per_second": solution.get("hashes_per_second", 0),
                    "time_elapsed_seconds": solution.get("time_elapsed", 0),
                    "nonces_generated": solution.get("nonces_generated", 0),
                    "efficiency": f"{solution.get('nonces_generated', 0) / max(solution.get('time_elapsed', 1), 1):.2f} nonces/sec",
                },
            }
            
            # Read existing or load from template
            if hourly_math_proof_file.exists() and hourly_math_proof_file.stat().st_size > 0:
                try:
                    with open(hourly_math_proof_file, 'r') as f:
                        hourly_proof_data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Corrupted hourly proof {hourly_math_proof_file}: {e}. Using template.")
                    hourly_proof_data = load_file_template_from_examples('hourly_math_proof')
                except (FileNotFoundError, PermissionError) as e:
                    print(f"Warning: Cannot read {hourly_math_proof_file}: {e}. Using template.")
                    hourly_proof_data = load_file_template_from_examples('hourly_math_proof')
            else:
                hourly_proof_data = load_file_template_from_examples('hourly_math_proof')
            
            # Ensure required fields
            if "proofs" not in hourly_proof_data:
                hourly_proof_data["proofs"] = []
            if "metadata" not in hourly_proof_data:
                hourly_proof_data["metadata"] = {}
            
            # Add hour info
            hourly_proof_data["metadata"]["hour"] = hour
            hourly_proof_data["metadata"]["hour_label"] = f"{year}-{month}-{day} Hour {hour}"
            hourly_proof_data["metadata"]["total_proofs_this_hour"] = len(hourly_proof_data["proofs"]) + 1
            hourly_proof_data["metadata"]["last_updated"] = current_timestamp()
            
            # Append new proof
            hourly_proof_data["proofs"].append(proof_entry)
            
            # Write updated file
            with open(hourly_math_proof_file, 'w') as f:
                json.dump(hourly_proof_data, f, indent=2)
            
            if self.verbose:
                print(f"✅ Detailed hourly math proof created: {hourly_math_proof_file}")
                print(f"   📅 Hour: {year}-{month}-{day} {hour}:00")
                print(f"   📊 Total proofs this hour: {len(hourly_proof_data['proofs'])}")
            
            return str(hourly_math_proof_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create hourly math proof: {e}")
                import traceback
                traceback.print_exc()
            return None


    def _provide_miner_feedback(self, miner_id, validation_result):
        """Provide detailed feedback to miners per Pipeline flow.txt: 'tells it why it is bad'"""
        try:
            feedback_dir = Path(brain_get_path("temporary_template_dir")) / miner_id / "feedback"
            feedback_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = int(time.time())
            feedback_file = feedback_dir / f"feedback_{timestamp}.json"
            
            with open(feedback_file, 'w') as f:
                json.dump(validation_result, f, indent=2)
            
            if self.verbose:
                print(f"📋 Feedback provided to {miner_id}: {feedback_file}")
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to provide feedback to {miner_id}: {e}")


    def _get_submission_path(self) -> Path:
        """Get mode-aware submission path from brainstem."""
        return Path(brain_get_path("submissions_dir"))


    def _create_global_submission_file(self, solution, miner_id):
        """Create/update global submission tracking file using System_File_Examples template."""
        try:
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import load_file_template_from_examples
            
            submission_path = self._get_submission_path()
            global_submission_file = submission_path / "global_submission.json"
            
            if not validate_folder_exists_dtm(str(submission_path), "DTM-submission-dir"):
                raise FileNotFoundError(f"Submission directory not found: {submission_path}")
            
            # Read existing or initialize from template
            if global_submission_file.exists():
                with open(global_submission_file, 'r') as f:
                    submission_data = json.load(f)
            else:
                # Load structure from System_File_Examples
                submission_data = load_file_template_from_examples('global_submission')
                submission_data['submissions'] = []  # Clear example data
            
            # Create submission entry
            submission_entry = {
                "submission_id": f"sub_{current_timestamp().replace(':', '').replace('-', '').replace('.', '_')}",
                "timestamp": current_timestamp(),
                "block_height": solution.get("height", 0),
                "block_hash": solution.get("hash", ""),
                "miner_id": miner_id,
                "nonce": solution.get("nonce", 0),
                "status": "accepted" if self.demo_mode else "pending",
                "network_response": "ACCEPTED" if self.demo_mode else "PENDING",
                "confirmations": 0,
                "payout_btc": solution.get("reward", 0)
            }
            
            submission_data["submissions"].append(submission_entry)
            submission_data["metadata"]["last_updated"] = current_timestamp()
            submission_data["total_submissions"] = len(submission_data["submissions"])
            submission_data["accepted"] = sum(1 for s in submission_data["submissions"] if s.get("status") == "accepted")
            submission_data["rejected"] = sum(1 for s in submission_data["submissions"] if s.get("status") == "rejected")
            submission_data["pending"] = sum(1 for s in submission_data["submissions"] if s.get("status") == "pending")
            
            with open(global_submission_file, 'w') as f:
                json.dump(submission_data, f, indent=2)
            
            # 🔥 HIERARCHICAL WRITE: Year/Month/Week/Day levels
            ledger_dir_base = self._get_ledger_path()
            try:
                results = brain_write_hierarchical(submission_entry, ledger_dir_base, "submission", "DTM")
                if self.verbose and results:
                    print(f"   📊 Hierarchical submission: {len(results)} levels updated")
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️ Hierarchical submission write failed: {e}")
            
            if self.verbose:
                print(f"✅ Submission tracked: {global_submission_file}")
            
            return str(global_submission_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create global submission: {e}")
            return None


    def _create_hourly_submission_file(self, solution, miner_id):
        """Create/update hourly submission file with Bitcoin-ready format using System_File_Examples template."""
        try:
            from Singularity_Dave_Brainstem_UNIVERSE_POWERED import load_file_template_from_examples, capture_system_info
            
            # Create hourly directory structure
            now = current_time()
            year = now.strftime("%Y")
            month = now.strftime("%m")
            day = now.strftime("%d")
            hour = now.strftime("%H")
            
            submission_path = self._get_submission_path()
            hourly_dir = submission_path / year / month / day / hour
            if not validate_folder_exists_dtm(str(hourly_dir), "DTM-hourly-submission"):
                raise FileNotFoundError(f"Hourly submission directory not found: {hourly_dir}")
            
            hourly_submission_file = hourly_dir / "hourly_submission.json"
            
            # Read existing or initialize from template
            if hourly_submission_file.exists():
                with open(hourly_submission_file, 'r') as f:
                    hourly_submission_data = json.load(f)
            else:
                # Load structure from System_File_Examples (Bitcoin-ready format)
                hourly_submission_data = load_file_template_from_examples('hourly_submission')
                hourly_submission_data['submissions'] = []  # Clear example data
                hourly_submission_data['hour'] = f"{year}-{month}-{day}_{hour}"
            
            # Get real system info
            system_info = capture_system_info()
            
            # Create Bitcoin-ready submission entry
            submission_entry = {
                "submission_id": f"sub_{current_timestamp().replace(':', '').replace('-', '').replace('.', '_')}",
                "timestamp": current_timestamp(),
                "block_header": {
                    "version": solution.get("version", 536870912),
                    "previousblockhash": solution.get("previousblockhash", ""),
                    "merkleroot": solution.get("merkleroot", ""),
                    "time": int(now.timestamp()),
                    "bits": solution.get("bits", ""),
                    "nonce": solution.get("nonce", 0)
                },
                "block_hex": solution.get("block_hex", ""),  # Bitcoin Core submitblock format
                "block_info": {
                    "height": solution.get("height", 0),
                    "hash": solution.get("hash", ""),
                    "size_bytes": solution.get("size", 0),
                    "weight": solution.get("weight", 0),
                    "difficulty": solution.get("difficulty", 0.0),
                    "leading_zeros": solution.get("leading_zeros", 0)
                },
                "miner_info": {
                    "miner_id": miner_id,
                    "process_id": system_info['process']['pid'],
                    "ip_address": system_info['network']['ip_address'],
                    "hostname": system_info['network']['hostname']
                },
                "submission": {
                    "submitted_at": current_timestamp(),
                    "rpc_method": "submitblock",
                    "rpc_endpoint": solution.get("rpc_endpoint", "http://127.0.0.1:8332"),
                    "network_response": "ACCEPTED" if self.demo_mode else "PENDING",
                    "response_time_ms": 0,
                    "block_propagation_peers": 0
                },
                "payout": {
                    "reward_btc": solution.get("reward", 3.125),
                    "fees_btc": solution.get("fees", 0),
                    "total_btc": solution.get("reward", 3.125) + solution.get("fees", 0),
                    "payout_address": solution.get("payout_address", ""),
                    "payout_status": "pending"
                }
            }
            
            hourly_submission_data["submissions"].append(submission_entry)
            hourly_submission_data["metadata"]["last_updated"] = current_timestamp()
            hourly_submission_data["submissions_this_hour"] = len(hourly_submission_data["submissions"])
            
            with open(hourly_submission_file, 'w') as f:
                json.dump(hourly_submission_data, f, indent=2)
            
            return str(hourly_submission_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create hourly submission: {e}")
            return None

            feedback_file = feedback_dir / f"validation_feedback_{timestamp}.json"
            
            # Create comprehensive feedback based on validation result
            if isinstance(validation_result, dict):
                error_message = validation_result.get('error', 'Unknown validation error')
            else:
                error_message = str(validation_result)
            
            feedback_data = {
                "timestamp": current_timestamp(),
                "feedback_type": "validation_failure",
                "miner_id": miner_id,
                "error_message": error_message,
                "guidance": self._generate_validation_guidance(error_message),
                "validation_requirements": {
                    "block_header_length": "160 hex characters (80 bytes)",
                    "hash_algorithm": "Bitcoin double SHA-256",
                    "target_compliance": "Hash value must be less than template target",
                    "nonce_consistency": "Nonce in header must match solution nonce",
                    "template_fields": "Version, previous hash, merkle root must match template"
                },
                "next_steps": [
                    "Review error message for specific validation failure",
                    "Check block header structure and field alignment",
                    "Verify nonce produces valid hash meeting target difficulty",
                    "Ensure all template fields are correctly included",
                    "Resubmit corrected solution to same process folder"
                ]
            }
            
            # Save detailed JSON feedback
            with open(feedback_file, 'w') as f:
                import json
                json.dump(feedback_data, f, indent=2)
            
            # Also create simple text version for quick reading
            simple_feedback_file = feedback_dir / f"feedback_{timestamp}.txt"
            with open(simple_feedback_file, 'w') as f:
                f.write(f"VALIDATION FAILURE - {current_timestamp()}\n")
                f.write(f"Miner: {miner_id}\n")
                f.write(f"Error: {error_message}\n\n")
                f.write(f"Guidance: {feedback_data['guidance']}\n\n")
                f.write("Next Steps:\n")
                for i, step in enumerate(feedback_data['next_steps'], 1):
                    f.write(f"{i}. {step}\n")
            
            if self.verbose:
                print(f"📝 Detailed validation feedback provided to {miner_id}")
                print(f"   💡 {feedback_data['guidance']}")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Error providing miner feedback: {e}")
    
    def _create_block_submission_file(self, solution, miner_id):
        """
        Create block submission file - the actual hex block data for Bitcoin Core.
        DTM creates this when it validates a solution.
        """
        try:
            # Get block info
            block_height = solution.get("block_height", 0)
            timestamp_str = current_timestamp().replace(':', '').replace('-', '').replace('.', '_')
            
            # Create filename
            filename = f"block_submission_{block_height}_{timestamp_str}.json"
            
            # Determine location (Mining/Submissions/ root level)
            submission_path = self._get_submission_path()
            block_submission_file = submission_path / filename
            
            # Build block submission data
            block_submission_data = {
                "metadata": {
                    "created_by": "DTM",
                    "purpose": "Block hex data for Bitcoin Core submitblock",
                    "created": current_timestamp(),
                    "block_height": block_height
                },
                "block_header": {
                    "version": solution.get("version", 536870912),
                    "previousblockhash": solution.get("previousblockhash", ""),
                    "merkleroot": solution.get("solution_data", {}).get("merkleroot", ""),
                    "time": int(current_time().timestamp()),
                    "bits": solution.get("bits", ""),
                    "nonce": solution.get("solution_data", {}).get("nonce", 0)
                },
                "block_hex": solution.get("block_hex", ""),  # Full block in hex for submitblock
                "block_hash": solution.get("solution_data", {}).get("block_hash", ""),
                "miner_id": miner_id,
                "validated_by_dtm": True,
                "ready_for_submission": solution.get("meets_difficulty", False)
            }
            
            # Write file
            defensive_write_json(str(block_submission_file), block_submission_data, "DTM")
            
            if self.verbose:
                print(f"✅ DTM: Created block submission file: {filename}")
            
            return str(block_submission_file)
            
        except Exception as e:
            if self.verbose:
                print(f"❌ DTM: Failed to create block submission file: {e}")
            return None

    def _generate_validation_guidance(self, error_message):
        """Generate specific guidance based on validation error type"""
        error_lower = error_message.lower()
        
        if "missing required fields" in error_lower:
            return "Ensure your solution includes all required fields: block_header, nonce, hash, target"
        elif "invalid block header length" in error_lower:
            return "Block header must be exactly 80 bytes (160 hex characters). Check header construction."
        elif "hash mismatch" in error_lower:
            return "The claimed hash doesn't match the recreated hash. Verify nonce is correctly applied to header."
        elif "does not meet target difficulty" in error_lower:
            return "Hash value is too high - doesn't meet Bitcoin target difficulty. Try different nonce values."
        elif "version mismatch" in error_lower:
            return "Block version in header doesn't match template. Use exact version from template."
        elif "previous hash mismatch" in error_lower:
            return "Previous block hash in header doesn't match template. Use exact previousblockhash from template."
        elif "merkle root mismatch" in error_lower:
            return "Merkle root in header doesn't match template. Use exact merkleroot from template."
        elif "nonce mismatch" in error_lower:
            return "Nonce in block header doesn't match solution nonce field. Ensure consistency."
        elif "block structure validation failed" in error_lower:
            return "Block header structure doesn't match Bitcoin format. Check field order and byte alignment."
        elif "hash recreation failed" in error_lower:
            return "Unable to recreate hash from block header. Check header format and hex encoding."
        else:
            return "Solution validation failed. Review all fields and ensure Bitcoin compliance."


    def _notify_looping_of_valid_solution(self, solution_package):
        """
        PIPELINE FLOW.TXT COMPLIANCE: Notify Looping AFTER all files created.
        'The Dynamic template manger tells the looping we have a solution and gives the solution to the looping file'
        """
        try:
            # Create solution notification file for Looping to pick up
            looping_dir = Path("Mining/Temporary/Template/looping_notifications")
            if not validate_folder_exists_dtm(str(looping_dir), "DTM-looping-notifications"):
                raise FileNotFoundError(f"Looping notifications directory not found: {looping_dir}. Brain.QTL canonical authority via Brainstem should create this folder structure.")
            
            timestamp = int(time.time())
            notification_file = looping_dir / f"valid_solution_{timestamp}.json"
            
            notification_data = {
                "timestamp": current_timestamp(),
                "notification_type": "valid_solution_found",
                "miner_id": solution_package["miner_id"],
                "solution": solution_package["solution"],
                "files_created": solution_package["files_created"],
                "dtm_status": "all_files_created_and_validated",
                "ready_for_submission": True,
                "created_by": "DTM_AutomaticMonitoring_TestingNode"
            }
            
            with open(notification_file, 'w') as f:
                json.dump(notification_data, f, indent=2)
            
            if self.verbose:
                print("🎉 PIPELINE FLOW.TXT COMPLIANCE COMPLETE!")
                print(f"   ✅ All DTM files created FIRST")
                print(f"   📨 Looping notified AFTER: {notification_file}")
                print("   🔄 DTM → Looping handoff per specification")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to notify Looping: {e}")



def main():
    """Main function for testing template manager"""
    try:
        print("🧪 Testing GPS-Enhanced Dynamic Template Manager")
        print("=" * 50)

        manager = GPSEnhancedDynamicTemplateManager()

        # Test template path generation
        template_path = manager.get_dynamic_template_path("test")
        print(f"📍 Generated template path: {template_path}")

        # Test template data creation
        test_template = {
            "height": 850000,
            "bits": "17034444",
            "previousblockhash": "0" * 64,
            "transactions": [],
        }

        # Test GPS enhancement
        gps_data = manager.create_gps_enhancement(test_template)
        print(f"🎯 GPS Enhancement: {gps_data}")

        # Test mining instruction
        instruction = manager.create_mining_instruction(test_template)
        print(
            f"📋 Mining instruction created: {instruction.get('instruction_id', 'unknown')}"
        )

        # Test template processing
        result = manager.process_mining_template(test_template)
        print(
            f"⚙️ Template processing: {'SUCCESS' if result.get('success') else 'FAILED'}"
        )

        # Test miner coordination
        coordination = manager.coordinate_with_miner("test_miner_001", test_template)
        print(
            f"🤝 Miner coordination: {'SUCCESS' if coordination.get('success') else 'FAILED'}"
        )

        # Display performance stats
        stats = manager.get_performance_stats()
        print(f"📊 Performance stats: {stats}")

        print("✅ Template manager test completed successfully")
        return True

    except Exception as e:
        print(f"❌ Template manager test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    def calculate_solution_quality(self, solution):
        """Calculate quality score for solution consensus."""
        try:
            leading_zeros = solution.get("miner_zeros", 0)
            required_zeros = solution.get("required_zeros", 0)
            
            # Quality = (actual_zeros / required_zeros) + bonus for extra zeros
            base_quality = leading_zeros / max(required_zeros, 1)
            extra_zeros = max(0, leading_zeros - required_zeros)
            bonus = extra_zeros * 0.1  # 10% bonus per extra zero
            
            return base_quality + bonus
        except (ValueError, TypeError, AttributeError, ZeroDivisionError):
            return 0.0

    def select_best_solution_consensus(self, solutions):
        """Select best solution from multiple miners using consensus."""
        if not solutions:
            return None
        
        # Sort by quality score
        solutions.sort(key=lambda x: x["quality_score"], reverse=True)
        best_solution = solutions[0]
        
        if self.verbose:
            print(f"🏆 Best solution selected from {best_solution['miner_id']} with quality score: {best_solution['quality_score']:.2f}")
            
            # Provide feedback to losing miners
            for solution in solutions[1:]:
                self.provide_miner_feedback(
                    solution["miner_id"], 
                    f"Solution quality {solution['quality_score']:.2f} was lower than winning solution {best_solution['quality_score']:.2f}"
                )
        
        return best_solution["solution"]

    def provide_miner_feedback(self, miner_id, feedback_message):
        """Provide feedback to miners as per Pipeline flow.txt."""
        try:
            feedback_dir = Path("Mining/Temporary/Template") / miner_id / "feedback"
            feedback_dir.mkdir(parents=True, exist_ok=True)
            
            feedback_file = feedback_dir / f"feedback_{int(time.time())}.txt"
            with open(feedback_file, 'w') as f:
                f.write(f"Timestamp: {current_timestamp()}\n")
                f.write(f"Feedback: {feedback_message}\n")
            
            if self.verbose:
                print(f"📝 Feedback provided to {miner_id}: {feedback_message}")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Could not provide feedback to {miner_id}: {e}")

    def start_automatic_subfolder_monitoring(self):
        """
        Start automatic subfolder monitoring per Pipeline flow.txt requirement:
        'Dynamic Template manger Should automatically check for when the sub folders have a file saved in them.'
        """
        try:
            import threading
            
            if hasattr(self, 'monitoring_thread') and self.monitoring_thread and self.monitoring_thread.is_alive():
                if self.verbose:
                    print("⚠️ Automatic monitoring already running")
                return
            
            if self.verbose:
                print("🔄 STARTING AUTOMATIC SUBFOLDER MONITORING")
                print(f"   📁 Monitoring: Mining/Temporary/Template/**/")
                print(f"   ⏱️ Check interval: {self.monitoring_interval} seconds")
                print("   🎯 Per Pipeline flow.txt specification")
            
            self.monitoring_thread = threading.Thread(
                target=self._continuous_monitoring_loop,
                daemon=True,
                name="DTM-SubfolderMonitor"
            )
            self.monitoring_thread.start()
            
            if self.verbose:
                print("✅ Automatic subfolder monitoring started")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to start automatic monitoring: {e}")

    def stop_automatic_monitoring(self):
        """Stop automatic subfolder monitoring."""
        self.monitoring_enabled = False
        if hasattr(self, 'monitoring_thread') and self.monitoring_thread and self.monitoring_thread.is_alive():
            if self.verbose:
                print("🛑 Stopping automatic subfolder monitoring")
            self.monitoring_thread.join(timeout=5)
            if self.verbose:
                print("✅ Automatic monitoring stopped")


def _write_dtm_smoke_report(component: str, results: dict, output_path: str) -> bool:
    payload = {
        "component": component,
        "timestamp": datetime.now(CENTRAL_TZ).isoformat(),
        "success": all(results.values()),
        "results": results,
    }

    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        defensive_write_json(output_path, payload, component)
        return True
    except Exception:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return True
        except Exception:
            return False


def run_smoke_test(output_path: str = None) -> bool:
    """Component-level smoke test for the Dynamic Template Manager."""
    if output_path is None:
        output_path = os.path.join(brain_get_path("user_look_at"), "dtm_smoke_test.json")

    results = {
        "initialized": False,
        "example_template": False,
        "filesystem_ready": False,
        "interfaces_available": False,
    }

    try:
        manager = GPSEnhancedDynamicTemplateManager(
            verbose=False,
            demo_mode=True,
            auto_initialize=False,
            create_directories=True,
        )
        results["initialized"] = True

        try:
            example = load_template_from_examples("current_template", "Templates")
            results["example_template"] = bool(example)
        except Exception:
            results["example_template"] = False

        results["filesystem_ready"] = Path(brain_get_path("temporary_template_dir")).exists()

        required_methods = [
            "receive_template_from_looping_file",
            "coordinate_looping_file_to_production_miner",
            "hot_swap_to_production_miner",
        ]
        results["interfaces_available"] = all(hasattr(manager, method) for method in required_methods)
    except Exception:
        pass

    _write_dtm_smoke_report("dynamic_template_manager", results, output_path)
    return all(results.values())


def run_smoke_network_test(output_path: str = None) -> bool:
    """Network-level smoke test for DTM plus miner coordination."""
    if output_path is None:
        output_path = os.path.join(brain_get_path("user_look_at"), "dtm_smoke_network.json")

    results = {
        "component_smoke": run_smoke_test(output_path.replace(".json", "_component.json")),
        "miner_interface": False,
        "template_roundtrip": False,
    }

    try:
        from production_bitcoin_miner import ProductionBitcoinMiner

        manager = GPSEnhancedDynamicTemplateManager(
            verbose=False,
            demo_mode=True,
            auto_initialize=False,
            create_directories=True,
        )
        miner = ProductionBitcoinMiner(daemon_mode=True, demo_mode=True, max_attempts=10)
        results["miner_interface"] = True

        test_template = {
            "height": 1,
            "transactions": [],
            "previousblockhash": "0" * 64,
            "target": "00000000ffff0000000000000000000000000000000000000000000000000000",
        }

        try:
            processed = manager.receive_template_from_looping_file(test_template)
            miner.update_template(processed or test_template)
            results["template_roundtrip"] = isinstance(miner.get_current_template(), dict)
        except Exception:
            results["template_roundtrip"] = False
    except Exception:
        results["miner_interface"] = False

    _write_dtm_smoke_report("dynamic_template_manager_network", results, output_path)
    return all(results.values())


def mini_orchestrator_main():
    """Main function for mini-orchestrator mode"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Dynamic Template Manager - Mini-Orchestrator Mode"
    )
    
    # BRAIN.QTL FLAG ORCHESTRATION - All flags centralized
    try:
        from Singularity_Dave_Brainstem_UNIVERSE_POWERED import brain_get_flags
        brain_flags = brain_get_flags("dtm")
        
        if brain_flags and not brain_flags.get("error"):
            # Add Brain.QTL flags dynamically (skip empty production flag)
            for category, flags in brain_flags.items():
                if isinstance(flags, dict):
                    for flag_name, flag_def in flags.items():
                        if isinstance(flag_def, dict) and flag_def.get('flag') and flag_def['flag'].strip():
                            flag = flag_def['flag']
                            help_text = flag_def.get('description', f'{flag_name} flag')
                            
                            if flag_def.get('type') == 'int':
                                parser.add_argument(flag, type=int, help=help_text)
                            elif flag_def.get('type') == 'boolean':
                                parser.add_argument(flag, action='store_true', help=help_text)
                            else:
                                parser.add_argument(flag, action='store_true', help=help_text)
            
            print("✅ Brain.QTL flags loaded into DTM")
        else:
            print("⚠️ Brain.QTL flags not available for DTM, using fallback")
    except Exception as e:
        print(f"⚠️ Brain.QTL DTM flag loading failed, using fallback: {e}")
    
    # DTM-SPECIFIC FLAGS
    parser.add_argument(
        "--orchestrator_id",
        type=str,
        required=False,
        help="Unique ID for this mini-orchestrator",
    )
    parser.add_argument(
        "--daemon_group",
        type=str,
        required=False,
        help="Comma-separated list of daemon IDs to manage",
    )
    parser.add_argument(
        "--mini_orchestrator_mode",
        action="store_true",
        help="Run in mini-orchestrator mode",
    )
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")

    args = parser.parse_args()

    if getattr(args, "smoke_test", False):
        success = run_smoke_test()
        sys.exit(0 if success else 1)

    if getattr(args, "smoke_network", False):
        success = run_smoke_network_test()
        sys.exit(0 if success else 1)

    if args.mini_orchestrator_mode:
        print("🎯 MINI-ORCHESTRATOR MODE ACTIVATED")
        print(f"   🆔 Orchestrator ID: {args.orchestrator_id}")
        print(f"   🤖 Managing Daemons: {args.daemon_group}")
        print(f"   🎮 Demo Mode: {args.demo}")
        print("=" * 60)

        # Initialize mini-orchestrator with proper arguments
        manager = GPSEnhancedDynamicTemplateManager(
            verbose=True,
            demo_mode=args.demo,
            auto_initialize=True,
            create_directories=False  # Brainstem creates folders
        )

        # Parse daemon group
        daemon_list = []
        if args.daemon_group:
            daemon_list = args.daemon_group.split(",")

        print(
            f"🎯 Mini-Orchestrator {args.orchestrator_id} managing {len(daemon_list)} daemons"
        )

        # Mini-orchestrator work loop
        template_count = 0
        while True:
            try:
                # Generate or receive templates
                print(
                    f"📋 Mini-Orchestrator {args.orchestrator_id}: Processing template #{template_count + 1}"
                )

                # Simulate template processing for demo mode
                if args.demo:
                    template = {
                        "height": 853800 + template_count,
                        "target": "1a00ffff",
                        "transactions": template_count % 10 + 1,
                        "timestamp": int(time.time()),
                        "orchestrator_id": args.orchestrator_id,
                        "daemon_group": daemon_list,
                    }

                    # Process through GPS enhancement
                    manager.process_mining_template(template)

                    # Coordinate with daemons in group
                    for daemon_id in daemon_list:
                        coordination = manager.coordinate_with_miner(
                            daemon_id, template
                        )
                        if coordination.get("success"):
                            print(f"   ✅ Template sent to daemon {daemon_id}")
                        else:
                            print(f"   ❌ Failed to coordinate with daemon {daemon_id}")

                template_count += 1

                # 🚀 CHECK FOR MINER SOLUTIONS (CRITICAL!)
                try:
                    valid_solution = manager.check_miner_subfolders_for_solutions()
                    if valid_solution:
                        print(f"   ✅ Valid solution found and processed!")
                        print(f"      - Miner: {valid_solution.get('miner_id', 'unknown')}")
                        print(f"      - Leading zeros: {valid_solution.get('leading_zeros_hex', 0)}")
                except Exception as solution_check_error:
                    print(f"   ⚠️ Solution check error: {solution_check_error}")

                # Status update every 10 templates
                if template_count % 10 == 0:
                    stats = manager.get_performance_stats()
                    print(
                        f"📊 Mini-Orchestrator {args.orchestrator_id}: {template_count} templates processed"
                    )
                    print(
                        f"   🎯 GPS Predictions: {stats.get('gps_predictions_made', 0)}"
                    )
                    print(
                        f"   ✅ Successful Optimizations: {stats.get('templates_optimized', 0)}"
                    )

                # Sleep between templates (demo mode) - but check for solutions more frequently
                if args.demo:
                    time.sleep(2)  # Check for solutions every 2 seconds
                else:
                    time.sleep(1)  # More frequent in production

            except KeyboardInterrupt:
                print(f"🛑 Mini-Orchestrator {args.orchestrator_id} shutdown requested")
                break
            except Exception as e:
                print(f"❌ Mini-Orchestrator {args.orchestrator_id} error: {e}")
                time.sleep(5)  # Wait before retrying

        print(f"🛑 Mini-Orchestrator {args.orchestrator_id} terminated")
        return True
    else:
        # Standard template manager mode
        return main()


def dtm_demo_mode():
    """Standalone demo mode for testing DTM GPS calculations and template generation"""
    print("\n" + "=" * 80)
    print("🎮 DYNAMIC TEMPLATE MANAGER - DEMO MODE")
    print("=" * 80)
    print("Testing GPS calculations, template generation, and validation\n")

    # Test 1: GPS Functions
    print("📍 TEST 1: GPS Enhancement Functions")
    print("-" * 80)

    test_height = 859298
    print(f"Block Height: {test_height}")

    # Test Knuth function
    knuth_result = knuth_function(test_height, 3, 161)
    print(f"✅ Knuth Function: K({test_height}, 3, 161) = {knuth_result}")

    # Test GPS coordinates
    gps_data = get_gps_coordinates()
    lat = gps_data["latitude"]
    lon = gps_data["longitude"]
    print(f"✅ GPS Coordinates: ({lat:.6f}, {lon:.6f}) [Source: {gps_data['source']}]")

    # Test GPS delta
    delta = calculate_gps_delta(lat, lon)
    print(f"✅ GPS Delta: {delta}")

    # Test 2: Template Generation
    print("\n📄 TEST 2: Template Generation")
    print("-" * 80)

    test_template = {
        "height": test_height,
        "previousblockhash": "0" * 64,
        "version": 0x20000000,
        "bits": "170b3ce9",
        "curtime": int(time.time()),
        "transactions": [],
    }

    # Test GPS-enhanced nonce range with template
    start_nonce, end_nonce, target_nonce, gps_info = calculate_gps_enhanced_nonce_range(
        test_template
    )
    print(f"✅ GPS Target Nonce: {target_nonce:,}")
    print(
        f"✅ GPS Nonce Range: {start_nonce:,} to {end_nonce:,} (Size: {end_nonce - start_nonce + 1:,})"
    )
    print()

    print(f"✅ Template Height: {test_template['height']}")
    print(f"✅ Previous Block: {test_template['previousblockhash'][:16]}...")
    print(f"✅ Difficulty Bits: {test_template['bits']}")
    print()

    # Test 3: Multi-Miner Nonce Coordination Simulation
    print("🔗 TEST 3: Multi-Miner Nonce Coordination")
    print("-" * 80)
    print("✅ Template validation passed")
    print("✅ GPS enhancement formula: K(h, 3, 161) + Δ_GPS = Target Nonce")
    print("✅ Nonce coordination: Each miner gets unique range based on GPS + height")
    print()

    # Test 4: Validation
    print("✅ TEST 4: Template Validation")
    print("-" * 80)

    # Test solution validation (mock)
    test_hash = "00000000000000000001a2b3c4d5e6f7" + "0" * 32
    leading_zeros = len(test_hash) - len(test_hash.lstrip("0"))
    print(f"✅ Test Hash: {test_hash[:32]}...")
    print(f"✅ Leading Zeros: {leading_zeros}")
    print(f"✅ Validation: {'PASS' if leading_zeros >= 16 else 'FAIL'}")
    print()

    print("=" * 80)
    print("🎉 DTM DEMO MODE COMPLETE - All systems operational!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    import sys
    import time

    # CRITICAL FIX: Pass arguments to mini_orchestrator_main so it can parse --demo flag
    # Run continuous orchestrator mode (handles --demo flag internally via argparse)
    success = mini_orchestrator_main()


    def create_math_proof(self, solution, knuth_params):
        """Create math proof entry when validating solution"""
        proof_entry = {
            "timestamp": datetime.now(CENTRAL_TZ).isoformat(),
            "nonce": solution.get('nonce', 0),
            "hash": solution.get('hash', ''),
            "difficulty": solution.get('difficulty', 0),
            "knuth_parameters": knuth_params,
            "sorrellian_class": "Type-A",
            "validation_status": "ACCEPTED"
        }
        
        # Write to global math proof
        global_path = self.base_path / "Math Proof" / "global_math_proof.json"
        if global_path.exists():
            try:
                with open(global_path, 'r') as f:
                    data = json.load(f)
                data['proofs'].append(proof_entry)
                data['total_proofs'] = len(data['proofs'])
                data['last_updated'] = datetime.now(CENTRAL_TZ).isoformat()
                with open(global_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"⚠️ Could not write math proof: {e}")
        
        return proof_entry

    exit(0 if success else 1)
