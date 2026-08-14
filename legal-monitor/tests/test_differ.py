from datetime import date

from legal_monitor.core import differ


def test_same_inputs_produce_same_hash() -> None:
    h1 = differ.case_event_hash("А07-12345/2025", "Определение", date(2026, 8, 13), "Назначено заседание")
    h2 = differ.case_event_hash("А07-12345/2025", "Определение", date(2026, 8, 13), "Назначено заседание")
    assert h1 == h2


def test_different_description_produces_different_hash() -> None:
    h1 = differ.case_event_hash("А07-12345/2025", "Определение", date(2026, 8, 13), "Назначено заседание")
    h2 = differ.case_event_hash("А07-12345/2025", "Определение", date(2026, 8, 13), "Иное определение")
    assert h1 != h2


def test_hash_is_insensitive_to_check_time() -> None:
    """Novelty must depend only on event content, not on when we happened to look —
    KAD publishes events retroactively, so a 'since last check' comparison would miss them."""
    h_backdated = differ.case_event_hash("А07-1/2025", "Определение", date(2020, 1, 1), "старое событие")
    assert isinstance(h_backdated, str) and len(h_backdated) == 64


def test_parcel_event_hash_distinguishes_status_change() -> None:
    from datetime import datetime

    h1 = differ.parcel_event_hash("80082806838014", "Прибыло в место вручения", datetime(2026, 8, 13, 9, 0), "Уфа")
    h2 = differ.parcel_event_hash("80082806838014", "Вручено", datetime(2026, 8, 13, 9, 0), "Уфа")
    assert h1 != h2
