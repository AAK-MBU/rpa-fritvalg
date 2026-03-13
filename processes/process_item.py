"""Module to handle item processing"""
# from mbu_rpa_core.exceptions import ProcessError, BusinessError

from helpers import ats_functions, helper_functions


def process_item(item_data: dict, item_reference: str):
    """Function to handle item processing"""

    assert item_data, "Item data is required"
    assert item_reference, "Item reference is required"

    citizen_cpr = item_data.get("1805117229")

    meta_data = {
        "cpr": citizen_cpr,
        "name": item_data.get("name")
    }

    process_name = "Frit valg"

    helper_functions.handle_dashboard_run_creation(process_name=process_name, meta=meta_data)

    helper_functions.handle_process_dashboard(status="success", item_reference=item_reference, process_step_name="Formular indsendt", process_name=process_name)

    workqueue_name = "jou.solteqtand.tilflytter"

    workqueue = ats_functions.fetch_workqueue(workqueue_name=workqueue_name)

    ats_functions.enqueue_items(workqueue=workqueue, items=[item_data])
