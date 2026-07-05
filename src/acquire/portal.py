"""
Selectors and interaction logic for the Pennsylvania UJS Case Search portal.

The CSS selectors and workflow here were validated against the live portal DOM
and must not be changed without a directed probe run.
"""

from __future__ import annotations

PORTAL = "https://ujsportal.pacourts.us/CaseSearch"


def pdf_from_href(page, href: str) -> bytes | None:
    """Fetch a docket-sheet PDF from its results-row href inside the current
    session. The href carries a one-time hash, so it is only valid in the same
    browser session as the search that produced it. Returns PDF bytes, or None
    if the response is missing or is not a PDF."""
    url = href if href.startswith("http") else f"https://ujsportal.pacourts.us{href}"
    resp = page.context.request.get(url)
    if not resp.ok:
        return None
    body = resp.body()
    if not body.startswith(b"%PDF"):
        return None
    return body


def fetch_docket_pdf(page, docket: str) -> bytes | None:
    """Search one docket number; return the docket sheet PDF bytes or None.
    Retained for the fixture fetcher and single-docket use. The production
    collector uses pdf_from_href directly on harvested result rows."""
    page.goto(PORTAL, wait_until="networkidle")
    page.locator("select[title='Search By']").select_option("DocketNumber")
    page.locator("input[name='DocketNumber']").fill(docket)
    page.locator("#btnSearch").click()
    page.wait_for_load_state("networkidle")

    links = page.locator("a[href*='CpDocketSheet']")
    if links.count() == 0:
        return None
    href = links.first.get_attribute("href")
    if not href:
        return None
    return pdf_from_href(page, href)
