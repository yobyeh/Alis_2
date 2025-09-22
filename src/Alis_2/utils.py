def deep_get(dct: dict, keys: list[str], default=None):
    cur = dct
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return default
    return default if cur is None else cur
