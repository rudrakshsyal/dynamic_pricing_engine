"""Read-only interface between the demo UI and DPE evidence."""

from src.rca_evidence import EvidenceStore


def get_date_evidence(departure_date: str) -> dict:
    """Return saved evidence and validation checks for one date."""
    store = EvidenceStore()
    return store.explain(departure_date)
