from __future__ import annotations

import pytest

from boundaryloop.demo import prepare


@pytest.fixture
def project(tmp_path):
    cfg = prepare(tmp_path)
    return tmp_path, cfg
