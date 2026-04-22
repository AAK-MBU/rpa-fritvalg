"""Module to handle item processing"""

import logging
import os
import sys

from mbu_solteqtand_shared_components.database.db_handler import SolteqTandDatabase
from mbu_rpa_core.exceptions import BusinessError

from helpers import ats_functions, helper_functions, solteq_helper
from processes.application_handler import get_app

logger = logging.getLogger(__name__)


def process_item(item_data: dict, item_reference: str):
    """Function to handle item processing"""

    assert item_data, "Item data is required"
    assert item_reference, "Item reference is required"

    try:
        citizen_cpr = item_data.get("cpr")

        meta_data = {
            "cpr": citizen_cpr,
            "name": item_data.get("name")
        }

        process_step_name = ""

        if "--fritvalg_registreret" in sys.argv:
            process_step_name = "Formular indsendt"

            helper_functions.handle_dashboard_run_creation(process_name="Frit valg", meta=meta_data)

            helper_functions.handle_process_dashboard(status="success", cpr=citizen_cpr, process_step_name=process_step_name)

            logger.info("after handle update")

            for workqueue_name in ["tan.fritvalg.faglig_vurdering_udfoert", "jou.solteqtand.fritvalg"]:
                workqueue = ats_functions.fetch_workqueue(workqueue_name=workqueue_name, dev=True)

                logger.info(f"workqueue: {workqueue}")

                ats_functions.enqueue_items(workqueue=workqueue, items=[item_data])
                logger.info("after enqueue items")

        elif "--faglig_vurdering_udfoert" in sys.argv:
            process_step_name = "Faglig vurdering"

            helper_functions.handle_process_dashboard(status="running", cpr=citizen_cpr, process_step_name=process_step_name)

            db_conn_string = os.getenv("DBCONNECTIONSTRINGSOLTEQTAND")
            solteq_tand_db_object = SolteqTandDatabase(conn_str=db_conn_string)

            filters = {
                "e.currentStateText": "Fritvalgsordning godkendt",
                "p.cpr": citizen_cpr,
                "e.archived": 0,
            }

            results = solteq_tand_db_object.get_list_of_events(filters=filters)

            if not results:
                raise BusinessError(message="Faglig vurdering endnu ikke udført")

            if len(results) > 1:
                raise BusinessError(message="Borgeren har mere end 1 'Fritvalgsordning godkendt'-hændelse!")

            helper_functions.handle_process_dashboard(status="success", cpr=citizen_cpr, process_step_name=process_step_name)

            digital_post_status = solteq_helper.check_digital_post_status(solteq_tand_db_object=solteq_tand_db_object, cpr=citizen_cpr)

            if not digital_post_status:
                raise BusinessError(message="Borger ikke tilmeldt digital post")

            solteq_app = get_app()

            solteq_app.open_patient(ssn=citizen_cpr)

            approval_document_name = solteq_helper.check_and_create_approval_document(
                solteq_app=solteq_app,
                solteq_tand_db_object=solteq_tand_db_object,
                item_data=item_data,
            )

            process_step_name = "Borger orienteret om aftale"

            solteq_helper.check_and_send_approval_document(
                solteq_app=solteq_app,
                solteq_tand_db_object=solteq_tand_db_object,
                item_data=item_data,
                approval_document_name=approval_document_name
            )

            solteq_helper.check_and_handle_event(
                solteq_app=solteq_app,
                solteq_tand_db_object=solteq_tand_db_object,
                cpr=citizen_cpr,
                event_name="Fritvalgsordning godkendt"
            )

            helper_functions.handle_process_dashboard(status="success", cpr=citizen_cpr, process_step_name=process_step_name)

    except BusinessError as be:
        logger.info(f"BusinessError: {be}")

        if str(be) == "Faglig vurdering endnu ikke udført":
            helper_functions.handle_process_dashboard(status="pending", cpr=citizen_cpr, process_step_name="Faglig vurdering", failure=be)

        elif str(be) == "Borger ikke tilmeldt digital post":
            helper_functions.handle_process_dashboard(status="optional", cpr=citizen_cpr, process_step_name="Borger orienteret om aftale", failure=be)

        else:
            helper_functions.handle_process_dashboard(status="failed", cpr=citizen_cpr, process_step_name=process_step_name, failure=be)

        raise

    except Exception as e:
        logger.exception(f"Unexpected error while processing item: {e}")

        helper_functions.handle_process_dashboard(status="failed", cpr=citizen_cpr, process_step_name=process_step_name, failure=e)

        raise
