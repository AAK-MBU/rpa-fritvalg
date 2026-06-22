"""Helper functions"""

import os
import logging

from datetime import date

from dotenv import load_dotenv
from mbu_process_dashboard_shared_components.process_dashboard_client import ProcessDashboardClient
from mbu_process_dashboard_shared_components import (
    process_run,
    process_step_run,
)

load_dotenv()

logger = logging.getLogger(__name__)

API_ADMIN_TOKEN = os.getenv("API_ADMIN_TOKEN")
CLIENT = ProcessDashboardClient(api_admin_token=API_ADMIN_TOKEN, base_url="https://dev-mbu-dashboard-api.adm.aarhuskommune.dk/api/v1")


def handle_dashboard_run_creation(process_name: str, meta: dict):
    """
    Method for handling the creation of new process dashboard runs - if run already exists for the citizen, no new process run is created
    """

    print(f"meta: {meta}")

    citizen_cpr = meta.get("cpr")

    existing_run_id = process_run.get_process_run_by_cpr(client=CLIENT, process_name=process_name, cpr=citizen_cpr)

    if existing_run_id:
        logger.info("Process run already exists for citizen")

    else:
        process_run.create_dashboard_run(client=CLIENT, process_name=process_name, meta=meta)


def handle_process_dashboard(status: str, cpr: str, process_step_name: str, failure: Exception | None = None, process_name: str = "Frit valg"):
    """
    Method for handling updating the process dashboard
    """

    status_update_data = {
        "status": status
    }

    step_run_id = process_step_run.get_step_run_id_for_process_step_cpr(client=CLIENT, process_name=process_name, step_name=process_step_name, cpr=cpr)

    if failure:
        step_run_update_data = process_step_run.build_step_run_update(status=status, failure=failure)

        status_update_data["failure"] = failure

    else:
        step_run_update_data = process_step_run.build_step_run_update(status=status)

    updated_step_run_data, status_code = process_step_run.update_dashboard_step_run_by_id(client=CLIENT, step_run_id=step_run_id, update_data=step_run_update_data)

    return updated_step_run_data, status_code


def is_16_or_older(cpr: str, on_date: date | None = None) -> bool:
    """
    Returns True if the citizen is 16 years old or older, based on their CPR number.

    Args:
        cpr: Danish CPR number, with or without a dash (e.g. "010190-1234" or "0101901234").
        on_date: The reference date to calculate age against. Defaults to today.

    Returns:
        True if the citizen is >= 16 years old, False otherwise.

    Raises:
        ValueError: If the CPR number is not a valid 10-digit format.
    """
    s = cpr.replace("-", "").strip()

    if len(s) != 10 or not s.isdigit():
        raise ValueError("Invalid CPR format")

    dd = int(s[0:2])
    mm = int(s[2:4])
    yy = int(s[4:6])
    serial = int(s[6:10])

    if 0 <= serial <= 3999:
        year = 1900 + yy
    elif 4000 <= serial <= 4999:
        year = 2000 + yy if yy <= 36 else 1900 + yy
    elif 5000 <= serial <= 8999:
        year = 2000 + yy if yy <= 57 else 1800 + yy
    else:
        year = 2000 + yy if yy <= 36 else 1900 + yy

    birthdate = date(year, mm, dd)
    today = on_date or date.today()

    age_years = today.year - birthdate.year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        age_years -= 1

    return age_years >= 16
