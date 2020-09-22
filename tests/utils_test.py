# -*- coding: utf-8 -*-
import os
import sys
from os.path import basename
from unittest import mock
from urllib.parse import urljoin
from urllib.request import pathname2url

import pytest

from language_formatters_pre_commit_hooks.utils import download_url
from language_formatters_pre_commit_hooks.utils import run_command


@pytest.mark.parametrize(
    "command, expected_status, expected_output",
    [
        ("echo 1", 0, "1{}".format(os.linesep)),
        pytest.param(
            "echo 1 | grep 0",
            1,
            "",
            marks=pytest.mark.skipif(condition=sys.platform == "win32", reason="Windows does not have `grep`"),
        ),
        pytest.param(
            "echo 1 | findstr 0",
            1,
            "",
            marks=pytest.mark.skipif(condition=sys.platform != "win32", reason="Linux and MacOS does not have `findstr`"),
        ),
        ["true", 0, ""],
        ["false", 1, ""],
    ],
)
def test_run_command(command, expected_status, expected_output):
    assert run_command(command) == (expected_status, expected_output)


@pytest.mark.parametrize(
    "url, does_file_already_exist",
    [
        [urljoin("file://", pathname2url(__file__)), True],
        [urljoin("file://", pathname2url(__file__)), False],
    ],
)
@mock.patch("language_formatters_pre_commit_hooks.utils.shutil", autospec=True)
@mock.patch("language_formatters_pre_commit_hooks.utils.requests", autospec=True)
def test_download_url(mock_requests, mock_shutil, tmpdir, url, does_file_already_exist):
    if does_file_already_exist:
        with open(os.path.join(tmpdir.strpath, basename(url)), "w") as f:
            f.write("")

    with mock.patch.dict(os.environ, {"PRE_COMMIT_HOME": tmpdir.strpath}):
        assert download_url(url) == os.path.join(tmpdir.strpath, basename(url))

    if does_file_already_exist:
        assert not mock_requests.get.called
    else:
        mock_requests.get.assert_called_once_with(url, stream=True)
