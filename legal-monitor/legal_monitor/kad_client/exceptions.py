class KadUnavailable(Exception):
    """KAD did not answer after a cookie refresh + retry. The whole KAD leg of
    this run should be skipped; the Pochta leg must still run."""


class KadResponseFormatUnknown(Exception):
    """The response was neither valid JSON nor HTML we recognise. Raised instead
    of guessing, so the caller logs it loudly and surfaces it in the Telegram
    summary rather than silently returning an empty result."""
