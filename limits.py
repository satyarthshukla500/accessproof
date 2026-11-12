import ipaddress
import time

_hits = {}


def net(ip):
    """The rate-limit key of an address: an IPv6 user owns a whole /64, so the key is the network, not the single address."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return ip or ""
    return str(ipaddress.ip_network("%s/64" % a, strict=False)) if a.version == 6 else str(a)


def count(key, window=600):
    """Number of hits for key in the last `window` seconds."""
    now = time.time()
    _hits[key] = [t for t in _hits.get(key, []) if now - t < window]
    return len(_hits[key])


def add(key):
    _hits.setdefault(key, []).append(time.time())
    if len(_hits) > 5000:  # forget keys with no recent hits; live lockouts stay
        now = time.time()
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 600]:
            del _hits[k]


def rate_limited(key, limit=10, window=600):
    """Counts this call and says whether the key is over its limit."""
    if count(key, window) >= limit:
        return True
    add(key)
    return False
