from __future__ import annotations

import re


CURRENT_VERSION = "2.1.0"


def version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value or "")
    return tuple(int(number) for number in numbers[:3]) or (0,)
