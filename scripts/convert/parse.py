"""
Unified rule parser for upstream proxy rule list files.

Handles formats:
  - Clash/Surge .list:  RULE_TYPE,VALUE[,POLICY[,extra]]
  - YAML payload:       payload:\n  - RULE_TYPE,VALUE
  - Loyalsoldier YAML:  payload:\n  - '+.domain.com'  (= DOMAIN-SUFFIX)
  - Raw domain lines:   domain.com  (treated as DOMAIN-SUFFIX)
  - QuantumultX:        ip-asn,<asn>,<policy>  (lowercase; policy stripped)

Skipped rule types: USER-AGENT, URL-REGEX, DEST-PORT, SRC-PORT, GEOIP, GEOSITE,
                    AND, OR, NOT, RULE-SET, FINAL, MATCH

Source URL schemes:
  - https://...          standard HTTP fetch
  - repo:owner/repo/ref/path  read from vendor/{owner}/{repo} via git-show;
                              falls back to raw.githubusercontent.com if not cloned
"""

import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Iterator

_REPO_ROOT = Path(__file__).parent.parent.parent

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
    "IP-ASN",        # classical only; value: "<asn>" or "<asn>,no-resolve"
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
    "RULE-SET",
    "FINAL",
    "MATCH",
    "NO-RESOLVE",  # not a real type; sometimes appears as suffix
}

_DOMAIN_RE = re.compile(
    r"^(?!\-)([a-zA-Z0-9\-*_]+\.)+[a-zA-Z]{2,}$"
)

_CIDR4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")
_CIDR6_RE = re.compile(r"^[0-9a-fA-F:]+:[0-9a-fA-F:]*/\d{1,3}$")


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
            # preserve no-resolve flag for IP-CIDR and IP-ASN
            if rule_type in ("IP-CIDR", "IP-CIDR6", "IP6-CIDR", "IP-ASN") and len(parts) >= 3:
                flag = parts[-1].strip().upper()
                if flag == "NO-RESOLVE":
                    value = f"{value},no-resolve"
                # For IP-ASN: if third field is not NO-RESOLVE, it's a QX policy name — strip it
            yield (rule_type, value)
            continue

        # bare domain (no RULE_TYPE prefix), only outside yaml payload context
        if not in_payload and _is_bare_domain(parts[0]):
            yield ("DOMAIN-SUFFIX", parts[0].strip())
            continue

        # bare CIDR lines (e.g. Loyalsoldier geoip text files: '1.0.1.0/24')
        bare = parts[0].strip()
        if _CIDR4_RE.match(bare):
            yield ("IP-CIDR", bare)
            continue
        if _CIDR6_RE.match(bare):
            yield ("IP-CIDR6", bare)
            continue

        # unknown type — skip silently


def _repo_url_to_http(url: str) -> str:
    """Convert repo:owner/repo/ref/path to https://raw.githubusercontent.com/..."""
    return "https://raw.githubusercontent.com/" + url[5:]


def _read_repo_local(url: str) -> str | None:
    """
    Read a repo: URL from a local vendor clone.

    Tries the filesystem (working tree) first — works for any --depth=1 clone.
    Falls back to git-show for edge cases (e.g. non-default-branch clones).
    Returns file text on success, None if vendor not available.
    """
    import urllib.parse
    # url format: repo:owner/repo/ref/path/to/file
    rest = url[5:]
    parts = rest.split("/", 3)
    if len(parts) < 4:
        return None
    owner, repo, ref, path = parts
    # Decode %xx sequences — categories.yaml may have URL-encoded spaces/chars
    path = urllib.parse.unquote(path)
    vendor_dir = _REPO_ROOT / "vendor" / owner / repo
    if not vendor_dir.exists():
        return None

    # Fast path: read from working tree directly (no subprocess needed)
    file_path = vendor_dir / path
    if file_path.exists():
        return file_path.read_text(encoding="utf-8", errors="replace")

    # Fallback: git-show (handles non-checked-out refs, symlinks, etc.)
    for git_ref in (ref, f"origin/{ref}", "origin/HEAD"):
        result = subprocess.run(
            ["git", "show", f"{git_ref}:{path}"],
            cwd=vendor_dir,
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout
    return None


def _read_http_local(url: str) -> str | None:
    """
    Check vendor/http/{host}/{path} for a locally cached copy of an HTTP source.
    Returns file text if cache exists, None otherwise.
    """
    import urllib.parse as _up
    parsed = _up.urlparse(url)
    cache_path = _REPO_ROOT / "vendor" / "http" / (parsed.netloc + parsed.path)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    return None


def fetch_and_parse(url: str, timeout: int = 30) -> list[tuple[str, str]]:
    """Fetch a source URL (http:// or repo:) and return parsed (rule_type, value) list."""
    if url.startswith("repo:"):
        text = _read_repo_local(url)
        if text is not None:
            return list(parse_lines(text))
        # Fall back to HTTP — transparent for CI and missing vendor repos
        url = _repo_url_to_http(url)

    # Check local HTTP cache (populated by vendor_sync.py) before going online
    cached = _read_http_local(url)
    if cached is not None:
        return list(parse_lines(cached))

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
