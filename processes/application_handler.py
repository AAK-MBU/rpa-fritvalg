"""Module for handling application startup, and close"""

import logging
import subprocess as sp
from subprocess import CalledProcessError

import psutil
from mbu_dev_shared_components.database.connection import RPAConnection
from mbu_rpa_core.exceptions import BusinessError
from mbu_solteqtand_shared_components.application import SolteqTandApp
from mbu_solteqtand_shared_components.application.exceptions import (
    NotMatchingError,
    PatientNotFoundError,
)

from helpers import config

APP = None
logger = logging.getLogger(__name__)



def get_app():
    # ruff: noqa: PLW0602
    global APP
    return APP


def open_patient(cpr: str) -> SolteqTandApp:
    """Open a patient in Solteq Tand, guarding against a missing patient.

    Fetches the running application instance and opens the patient with the
    given CPR. Conditions that stem from the input data rather than an
    automation failure are translated into a ``BusinessError`` so they are
    handled as business failures upstream:

    - ``PatientNotFoundError``: no patient exists with the given CPR.
    - ``NotMatchingError``: a patient was opened, but its CPR did not match
      the requested one.

    Returns the application instance so callers can keep using it.
    """
    solteq_app = get_app()
    if solteq_app is None:
        raise ValueError("Could not get application instance.")

    logger.info("Opening patient in Solteq Tand application...")
    try:
        solteq_app.open_patient(cpr)
    except PatientNotFoundError as exc:
        raise BusinessError(f"Patient med CPR {cpr} findes ikke i Solteq Tand") from exc
    except NotMatchingError as exc:
        raise BusinessError(
            f"Opened patient's CPR did not match the requested CPR: {cpr}"
        ) from exc

    return solteq_app


def is_app_running() -> bool:
    """Return True if a tracked Solteq Tand instance exists and its process is alive.

    Guards against two stale states: no instance tracked yet, and a tracked
    instance whose process has since crashed/been closed (``APP`` still set but
    ``TMTand.exe`` gone) — both of which should trigger a fresh startup.
    """
    if get_app() is None:
        return False

    return any(p.info["name"] == "TMTand.exe" for p in psutil.process_iter(["name"]))


def startup():
    """Start Solteq Tand, reusing an existing instance if one is already running.

    Idempotent on purpose: processing several workitems in a single run calls
    ``startup()`` per item, and without this guard each call would spawn another
    application instance.
    """
    if is_app_running():
        logger.info("Solteq Tand is already running — reusing the existing instance.")
        return

    logger.info("Starting applications...")

    with RPAConnection(db_env="PROD", commit=False) as rpa_conn:
        creds = rpa_conn.get_credential("solteq_tand_svcrpambu001")
        username = creds["username"]
        password = creds["decrypted_password"]

    solteq_app = SolteqTandApp(
        app_path=config.APP_PATH,
        username=username,
        password=password
    )

    solteq_app.start_application()
    solteq_app.login()

    # ruff: noqa: PLW0603
    global APP
    APP = solteq_app


def soft_close():
    """Function for closing applications softly"""
    logger.info("Closing applications softly...")
    solteq_app = get_app()
    solteq_app.close_solteq_tand()
    logger.info("Closed application softly")


def hard_close():
    """Function for closing applications hard"""
    logger.info("Closing applications hard...")
    list_processes = ["wmic", "process", "get", "description"]
    if "TMTand.exe" in sp.check_output(list_processes).strip().decode():
        try:
            kill_msg = sp.check_output(["taskkill", "/f", "/im", "TMTand.exe"])

            logger.info(kill_msg)

        except CalledProcessError as e:
            logger.error(f"TMTand.exe found in subprocesses, but error while killing it: {e}")


def close():
    """Function for closing applications softly or hardly if necessary"""
    try:
        soft_close()
    except Exception:
        pass

    if any(p.info["name"] == "TMTand.exe" for p in psutil.process_iter(["name"])):
        logger.warning("App still running after soft close — falling back to hard close")
        hard_close()


def reset():
    """Function for resetting application"""
    close()
    startup()