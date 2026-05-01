"""
Unified rule parser for upstream proxy rule list files.

Handles formats:
  - Clash/Surge .list:  RULE_TYPE,VALUE[,POLICY[,extra]]
  - YAML payload:       payload:\n  - RULE_TYPE,VALUE
  - Loyalsoldier YAML:  payload:\n  - '+.domain.com'  (= DOMAIN-SUFFIX)
  - Raw domain lines:   domain.com  (treated as DOMAIN-SUFFIX)

Skipped rule types: USER-AGENT, URL-REGEX, DEST-PORT, SRC-PORT, GEOIP, GEOSITE,
                    AND, OR, NOT, IP-ASN, RULE-SET, FINAL, MATCH
"""

import re
import urllib.request
import urllib.error
from typing import Iterator

# Types emitted as-is into output
SUPPORTED_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "DOMAIN-REGEX",
    "IP-CIDR",
    "IP-CIDR6",
    "IP6-CIDR",
    "PROCESS-NAME",  # kept in classical; stripped from domain/ipcidr
}

# Types silently dropped
SKIP_TYPES = {
    "USER-AGENT",
    "URL-REGEX",
    "DEST-PORT",
    "SRC-PORT",
    "GEOIP",
    "GEOSITE",
    "AND",
    "OR",
    "NOT",
    "IP-ASN",
    "RULE-SET",
    "FINAL",
    "MATCH",
    "NO-RESOLVE",  # not a real type; sometimes appears as suffix
}

_DOMAIN_RE = re.compile(
    r"^(?!\-)([a-zA-Z0-9\-*_]+\.)+[a-zA-Z]{2,}$"
)


def _is_bare_domain(token: str) -> bool:
    return bool(_DOMAIN_RE.match(token))


def parse_lines(text: str) -> Iterator[tuple[str, str]]:
    """
    Yield (rule_type, value) tuples from a rule file text.
    IP-CIDR no-resolve flag is preserved as 'IP-CIDR,1.2.3.4/24,no-resolve'
    by returning value as '1.2.3.4/24' and attaching flag in the value itself
    via a separate 'no-resolve' annotation — callers must handle the third field.

    Actually we return (rule_type, value) where value may be 'x.x.x.x/yy,no-resolve'
    for IP-CIDR with no-resolve. Downstream emitters check for this.
    """
    in_payload = False

    for raw in text.splitlines():
        line = raw.strip()

        # blank / comment
        if not line or line.startswith("#") or line.startswith("//") or line.startswith("##"):
            continue

        # YAML payload marker
        if line == "payload:":
            in_payload = True
            continue

        if in_payload:
            # strip YAML list prefix and quotes
            if line.startswith("- "):
                line = line[2:].strip().strip("'\"")
            elif line.startswith("-"):
                line = line[1:].strip().strip("'\"")
            else:
                # indented non-list line inside payload block
                line = line.strip("'\"")

            # Loyalsoldier '+.domain' format → DOMAIN-SUFFIX
            if line.startswith("+."):
                yield ("DOMAIN-SUFFIX", line[2:])
                continue

        # Split on comma — RULE_TYPE,VALUE[,POLICY[,flags]]
        parts = line.split(",")
        rule_type = parts[0].strip().upper()

        if rule_type in SKIP_TYPES:
            continue

        if rule_type in SUPPORTED_TYPES:
            if len(parts) < 2:
                continue
            value = parts[1].strip()
            # preserve no-resolve as part of value for IP-CIDR
            if rule_type in ("IP-CIDR", "IP-CIDR6", "IP6-CIDR") and len(parts) >= 3:
                flag = parts[-1].strip().upper()
                if flag == "NO-RESOLVE":
                    value = f"{value},no-resolve"
            yield (rule_type, value)
            continue

        # bare domain (no RULE_TYPE prefix), only outside yaml payload context
        if not in_payload and _is_bare_domain(parts[0]):
            yield ("DOMAIN-SUFFIX", parts[0].strip())
            continue

        # unknown type — skip silently


def fetch_and_parse(url: str, timeout: int = 30) -> list[tuple[str, str]]:
    """Download a URL and return parsed (rule_type, value) list."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "hajimihomo/1.0 (github.com/cest-la-v/hajimihomo)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {url}") from e
    except Exception as e:
        raise RuntimeError(f"Error fetching {url}: {e}") from e

    return list(parse_lines(text))
