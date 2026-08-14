# kad.arbitr.ru — known endpoints

## POST /Kad/SearchInstances

Confirmed reachable and confirmed to enforce cookie-gating: an unauthenticated
POST (no `pr_fp`/`wasm`/DDoS-Guard cookies) returns **HTTP 451** with a
"Доступ к сервису ограничен" HTML page, served by `server: ddos-guard`. This
matches the brief's description of 451 = expired/missing cookies, not a
permanent block.

**Open question — response format on success.** The brief states the
endpoint returns HTML (BeautifulSoup row parsing). Independent recollection of
this site says `SearchInstances` has historically returned **JSON**
(`Result.Items[]` with `CaseNumber`, `CaseId`, `Courts[]`, `Judges[]`,
`Plaintiffs[]`, `Respondents[]`, ...). Neither could be confirmed here because
a valid, cookie-authenticated request was never made (see "What's blocked"
below). `legal_monitor/kad_client/parser.py` therefore detects the actual
shape at runtime and parses either; it raises `KadResponseFormatUnknown`
loudly if it recognises neither, rather than silently returning nothing.

**Action before production use:** run one real search once cookies work, save
the raw response body to `tests/fixtures/`, and delete whichever parsing
branch turns out to be dead code.

## Card page — GET /Card/{guid}

**Not investigated.** The brief requires this to be found by recording real
network traffic in a headful Playwright session against a real case. That
session could not be run here — see below. `legal_monitor/kad_client/card.py`
ships only the brief's documented fallback (full Playwright render + DOM
scrape of the card page), with CSS selectors that are an unverified best
guess at typical KAD markup, not captured from a live page.

**This is the top item for whoever picks this project up next**, per the
brief's own build order ("разведка карточки дела — самый неопределённый
этап"). Steps once a real browser session against kad.arbitr.ru is available:

1. `playwright.chromium.launch(headless=False)`, log all requests/responses.
2. Open `https://kad.arbitr.ru/Card/<a real case guid>`, wait for the events
   block to render.
3. Note which POST/GET returns the event list, with what body/headers.
4. Update `card.py` to call it directly over httpx (much faster than a full
   render per case), keep the DOM-scrape as fallback if it ever 404s.
5. Update this file with the date the endpoint was confirmed — it can change.
6. Capture a real card page (or the JSON, if found) into
   `tests/fixtures/` and extend `tests/test_parser.py`.

## What's blocked in the environment this was built in

Chromium (via Playwright) cannot complete a TLS handshake to kad.arbitr.ru —
or to any HTTPS host — through this sandbox's outbound proxy. Confirmed with
`chrome --log-net-log`: the ClientHello is sent, then the socket gets
`SOCKET_READ_ERROR net_error=-101` (`ECONNRESET`) before any ServerHello
comes back. `httpx` and `curl` through the exact same proxy work fine
(`kad.arbitr.ru/` returns HTTP 200), so the site itself is reachable — this is
specifically a Chromium/proxy TLS incompatibility in the sandbox, most likely
related to the size/shape of Chrome's post-quantum-hybrid ClientHello versus
what the proxy's TLS-terminating layer can parse. It is **not expected on the
customer's own always-on server**, which has no such intercepting proxy in
front of it. Run `python -m legal_monitor.cookie_service` there first, before
anything else — the whole project is built on the assumption that step works.

_Last checked: 2026-08-14._
