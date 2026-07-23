#!/usr/bin/env python3
"""Append new Google Scholar records to Publications.html as text-only entries."""

from __future__ import annotations

import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PROFILE_ID = "zgw0g40AAAAJ"
PROFILE_URL = (
    "https://scholar.google.com/citations"
    f"?user={PROFILE_ID}&hl=en&pagesize=100&sortby=pubdate"
)
PUBLICATIONS_PAGE = Path("Publications.html")
START = "<!-- AUTO-PUBLICATIONS:START -->"
END = "<!-- AUTO-PUBLICATIONS:END -->"


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def fetch_scholar() -> list[dict[str, str]]:
    response = requests.get(
        PROFILE_URL,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    records: list[dict[str, str]] = []

    for row in soup.select("tr.gsc_a_tr"):
        title_link = row.select_one("a.gsc_a_at")
        metadata = row.select("div.gs_gray")
        year_node = row.select_one("span.gsc_a_hc")
        if title_link is None or len(metadata) < 2:
            continue
        records.append(
            {
                "title": title_link.get_text(" ", strip=True),
                "authors": metadata[0].get_text(" ", strip=True),
                "venue": metadata[1].get_text(" ", strip=True),
                "year": year_node.get_text(" ", strip=True) if year_node else "",
                "url": urljoin("https://scholar.google.com", title_link.get("href", "")),
            }
        )

    if not records:
        raise RuntimeError("Google Scholar returned no publication records; page left unchanged")
    return records


def remove_generated_block(page: str) -> str:
    pattern = re.compile(
        rf"\s*{re.escape(START)}.*?{re.escape(END)}\s*", re.DOTALL
    )
    return pattern.sub("\n", page)


def render(records: list[dict[str, str]]) -> str:
    if not records:
        return f"{START}\n{END}"

    items = []
    for record in records:
        title = html.escape(record["title"])
        authors = html.escape(record["authors"])
        venue = html.escape(record["venue"])
        year = html.escape(record["year"])
        url = html.escape(record["url"], quote=True)
        year_text = f" ({year})" if year else ""
        items.append(
            "<article class=\"pub-auto-entry\">"
            f"<h3><a href=\"{url}\" target=\"_blank\" rel=\"noopener\">{title}</a></h3>"
            f"<p>{authors}</p><p><strong>{venue}</strong>{year_text}</p>"
            "</article>"
        )

    checked = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"{START}\n"
        "<section id=\"automatically-added-publications\" class=\"level2\">"
        "<h2>Recently added publications</h2>"
        "<p class=\"text-muted\">Automatically synchronized from "
        f"<a href=\"https://scholar.google.com/citations?user={PROFILE_ID}&amp;hl=en\" "
        "target=\"_blank\" rel=\"noopener\">Google Scholar</a>. "
        f"Last checked: {checked}.</p>"
        + "".join(items)
        + "</section>\n"
        f"{END}"
    )


def main() -> int:
    page = PUBLICATIONS_PAGE.read_text(encoding="utf-8")
    manual_page = remove_generated_block(page)
    manual_text = normalize(BeautifulSoup(manual_page, "html.parser").get_text(" "))
    records = fetch_scholar()
    new_records = [record for record in records if normalize(record["title"]) not in manual_text]

    block = render(new_records)
    if "</main>" not in manual_page:
        raise RuntimeError("Could not find the Publications page content boundary")
    updated = manual_page.replace("</main>", f"\n{block}\n</main>", 1)
    PUBLICATIONS_PAGE.write_text(updated, encoding="utf-8")
    print(f"Scholar records: {len(records)}; new text-only entries: {len(new_records)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Publication update stopped safely: {exc}", file=sys.stderr)
        raise SystemExit(1)
