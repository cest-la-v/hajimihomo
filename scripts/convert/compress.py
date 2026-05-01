"""
Semantic rule compression matching blackmatrix7 RULE GENERATOR operations:

1. DOMAIN-SUFFIX parent subsumption:
   Remove DOMAIN-SUFFIX,x.y if DOMAIN-SUFFIX,y already covers it.
   Remove DOMAIN,x.y       if DOMAIN-SUFFIX,y already covers it.

2. IP-CIDR(6) aggregation:
   Merge overlapping/adjacent ranges using ipaddress.collapse_addresses().
   IPv4/IPv6 and no-resolve vs normal handled separately to preserve semantics.
"""

import ipaddress


# ---------------------------------------------------------------------------
# Domain subsumption
# ---------------------------------------------------------------------------

def _normalize_domain(v: str) -> str:
    return v.lower().strip(".")


def _is_covered_by_suffix_set(value: str, suffix_set: set[str]) -> bool:
    """
    Return True if `value` is semantically covered by any entry in `suffix_set`.

    Coverage means `value == suffix` OR `value` ends with `.<suffix>` at a
    label boundary.  This prevents 'badapple.com' being matched by 'apple.com'.
    """
    v = _normalize_domain(value)
    if v in suffix_set:
        return True
    labels = v.split(".")
    for i in range(1, len(labels)):
        parent = ".".join(labels[i:])
        if parent in suffix_set:
            return True
    return False


def compress_domain(rules: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Remove rules subsumed by a broader DOMAIN-SUFFIX entry.

    Pass 1: build the full set of normalized DOMAIN-SUFFIX values.
    Pass 2: emit only rules not covered by a broader suffix.
    """
    suffix_set: set[str] = {
        _normalize_domain(v) for rt, v in rules if rt == "DOMAIN-SUFFIX"
    }

    result: list[tuple[str, str]] = []
    for rt, v in rules:
        v_norm = _normalize_domain(v)

        if rt == "DOMAIN-SUFFIX":
            # Remove if any STRICT PARENT suffix already covers us.
            # Split from index 1 so we never compare against ourselves.
            labels = v_norm.split(".")
            keep = True
            for i in range(1, len(labels)):
                parent = ".".join(labels[i:])
                if parent in suffix_set:
                    keep = False
                    break
            if keep:
                result.append((rt, v))

        elif rt == "DOMAIN":
            # Remove if any DOMAIN-SUFFIX already covers this exact hostname.
            if not _is_covered_by_suffix_set(v_norm, suffix_set):
                result.append((rt, v))

        else:
            result.append((rt, v))

    return result


# ---------------------------------------------------------------------------
# IP-CIDR aggregation
# ---------------------------------------------------------------------------

def compress_cidr(rules: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Aggregate overlapping/adjacent CIDR ranges.

    Splits into four buckets to preserve semantics:
      IPv4 plain, IPv4 no-resolve, IPv6 plain, IPv6 no-resolve.
    """
    buckets: dict[tuple[bool, bool], list[ipaddress.IPv4Network | ipaddress.IPv6Network]] = {
        (False, False): [],  # IPv4 plain
        (False, True):  [],  # IPv4 no-resolve
        (True,  False): [],  # IPv6 plain
        (True,  True):  [],  # IPv6 no-resolve
    }
    non_cidr: list[tuple[str, str]] = []

    for rt, v in rules:
        if rt not in ("IP-CIDR", "IP-CIDR6", "IP6-CIDR"):
            non_cidr.append((rt, v))
            continue

        no_resolve = v.endswith(",no-resolve")
        cidr_str = v.removesuffix(",no-resolve")
        try:
            net = ipaddress.ip_network(cidr_str, strict=False)
        except ValueError:
            # Malformed CIDR — keep as-is
            non_cidr.append((rt, v))
            continue

        is_v6 = isinstance(net, ipaddress.IPv6Network)
        buckets[(is_v6, no_resolve)].append(net)

    result = list(non_cidr)
    for (is_v6, no_resolve), nets in buckets.items():
        if not nets:
            continue
        suffix = ",no-resolve" if no_resolve else ""
        for net in ipaddress.collapse_addresses(nets):
            if is_v6:
                result.append(("IP-CIDR6", f"{net}{suffix}"))
            else:
                result.append(("IP-CIDR", f"{net}{suffix}"))

    return result


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------

def compress(rules: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Apply all compression passes in the correct order."""
    rules = compress_domain(rules)
    rules = compress_cidr(rules)
    return rules
