# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os

import pytest
from tomlkit import api
from tomlkit.items import AoT
from tomlkit.items import Array
from tomlkit.items import Bool
from tomlkit.items import Comment
from tomlkit.items import Float
from tomlkit.items import InlineTable
from tomlkit.items import Integer
from tomlkit.items import Key
from tomlkit.items import String
from tomlkit.items import Table

from language_formatters_pre_commit_hooks.pretty_format_toml import pretty_format_toml
from language_formatters_pre_commit_hooks.pretty_format_toml import PrettyTomlDocument
from tests import run_autofix_test


fail_because_tomlkit = pytest.mark.xfail(reason="Moving to tomlkit requires the implementation of some custom handling")


@pytest.fixture(autouse=True)
def change_dir():
    working_directory = os.getcwd()
    try:
        os.chdir("test-data/pretty_format_toml/")
        yield
    finally:
        os.chdir(working_directory)


class TestTomlKitPrettifiers(object):
    @pytest.fixture
    def doc(self):
        return PrettyTomlDocument("")

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("[[aot]]\nkey = 'value'", "[[aot]]\nkey = 'value'\n"),
            ("[[aot]]\nkey = +0", "[[aot]]\nkey = 0\n"),  # Ensure that we're prettifying the content as well
        ),
    )
    def test__prettify_aot(self, input_string, expected_output):
        doc = PrettyTomlDocument(input_string)
        # We need to access the body instead of using `api.value` because
        # the discrimination between Table and AoT depends on the outside context
        value = doc.root_container.body[0][1]
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, AoT)
        doc._prettify_aot(value)
        assert doc.dumps() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            # Ensure that we have a space after the separator (comma)
            ("[1, 2,3]", "[1, 2, 3]"),
            # Ensure that nested are acutally prettified
            ("[1, 2,0xa]", "[1, 2, 0xA]"),
            # Arrays are in a single line
            # For some reason multiline is not well parsed
            # TODO: We might want to fix this in the future
            ("[\n    1,\n\n    2,\n    0xa]", "[1, 2, 0xA]"),
        ),
    )
    def test__prettify_array(self, doc, input_string, expected_output):
        value = api.value(input_string)
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, Array)
        doc._prettify_array(value)
        assert value.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("true", "true"),
            ("false", "false"),
        ),
    )
    def test__prettify_bool(self, doc, input_string, expected_output):
        value = api.value(input_string)
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, Bool)
        doc._prettify_bool(value)
        assert value.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("# This is a comment", "# This is a comment"),
            ("    # This is a comment", "# This is a comment"),
        ),
    )
    def test__prettify_comment(self, input_string, expected_output):
        doc = PrettyTomlDocument(input_string)
        value = doc.root_container.body[0][1]
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, Comment)
        doc._prettify_comment(value)
        assert value.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("key", "key"),
            ("'key'", "key"),
            ('"key"', "key"),
            ('"key with space"', '"key with space"'),
            ("'key with space'", '"key with space"'),
        ),
    )
    def test__prettify_key(self, input_string, expected_output):
        doc = PrettyTomlDocument("{} = 1".format(input_string))
        key = doc.root_container.body[0][0]  # Extract the key from the tomlkit parsed document
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(key, Key)
        doc._prettify_key(key)
        assert key.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, indent_level, expected_output",
        (
            ("a = 1", 0, "a = 1"),
            ("a = 1", 1, " a = 1"),
            ("    a = 1", 1, " a = 1"),
        ),
    )
    def test__prettify_indentation(self, input_string, indent_level, expected_output):
        doc = PrettyTomlDocument(input_string)
        for _, value in doc.root_container.items():
            doc._prettify_indentation(value, indent_level)
        assert doc.root_container.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("a = 1# comment", "a = 1  # comment"),
            ("a = 1  #comment", "a = 1  # comment"),
            ("a = 1    #    comment", "a = 1  # comment"),
        ),
    )
    def test__prettify_inline_comment(self, input_string, expected_output):
        doc = PrettyTomlDocument(input_string)
        for _, value in doc.root_container.items():
            doc._prettify_inline_comment(value)
        assert doc.root_container.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("table = { key = 'table' }", "table = { key = 'table' }\n"),
            ("table = { key = +0 }", "table = { key = 0 }\n"),  # Ensure that we're prettifying the content as well
        ),
    )
    def test__prettify_inline_table(self, input_string, expected_output):
        doc = PrettyTomlDocument(input_string)
        value = doc.root_container.body[0][1]
        assert isinstance(value, InlineTable)
        doc._prettify_inline_table(value)
        assert doc.dumps() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("+0", "0"),
            ("-0", "0"),
            ("0", "0"),
            ("1", "1"),
            ("+2", "2"),
            ("-3", "-3"),
            ("0b0", "0"),
            ("0b101", "0b101"),
            ("0o0", "0"),
            ("0o00", "0"),
            ("0o234", "0o234"),
            ("0x0", "0"),
            ("0x00", "0"),
            ("0xabc", "0xABC"),
            # Separators
            ("4_5", "45"),
            ("0xab_c", "0xABC"),
            # Leading 0s
            ("0b01", "0b1"),
            ("0o02", "0o2"),
            ("0x0F", "0xF"),
        ),
    )
    def test__prettify_integer(self, doc, input_string, expected_output):
        value = api.value(input_string)
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, Integer)
        doc._prettify_integer(value)
        assert value.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("+0.00", "0.0"),
            ("-0.00", "0.0"),
            ("1.9", "1.9"),
            ("+2.1", "2.1"),
            ("-3.2", "-3.2"),
            ("0e2", "0.0"),
            ("-0e23141", "0.0"),
            ("1e2", "1e2"),
            ("3E4", "3e4"),
            # Separators
            ("1_2.3_4", "12.34"),
            # Leading 0s
            ("3e04", "3e4"),
            # Trailing 0s
            ("5.0", "5.0"),
            ("67.890", "67.89"),
        ),
    )
    def test__prettify_float(self, doc, input_string, expected_output):
        value = api.value(input_string)
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, Float)
        doc._prettify_float(value)
        assert value.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("'something'", "'something'"),
            ('"something"', '"something"'),
            (
                '''"""something on
multiple lines"""''',
                '''"""something on
multiple lines"""''',
            ),
            (
                """'''something on
multiple lines'''""",
                """'''something on
multiple lines'''""",
            ),
        ),
    )
    def test__prettify_string(self, doc, input_string, expected_output):
        value = api.value(input_string)
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, String)
        doc._prettify_string(value)
        assert value.as_string() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            ("[table]\n", "[table]\n"),
            ("[table]\nkey = 'value'\n", "[table]\nkey = 'value'\n"),
            ("[table]\n    key = 'value'\n", "[table]\nkey = 'value'\n"),
            ("[table]\nkey = +0\n", "[table]\nkey = 0\n"),  # Ensure that we're prettifying the content as well
        ),
    )
    def test__prettify_table(self, input_string, expected_output):
        doc = PrettyTomlDocument(input_string)
        value = doc.root_container.body[0][1]
        # Quick "runtime" type check to make sure we're not testing weird cases
        assert isinstance(value, Table)
        doc._prettify_table(value)
        assert doc.dumps() == expected_output

    @pytest.mark.parametrize(
        "input_string, expected_output",
        (
            # TODO: Add cases with multiple consecutive white lines.
            # TODO: Add test case with empty lines at the begin or end of the document
            # Boolean formatting
            ("key = true", "key = true\n"),
            ("key = false", "key = false\n"),
            # Comment formatting
            ("# This is a comment", "# This is a comment\n"),
            (" # This is a comment", "# This is a comment\n"),
            ("key = 'value'# This is a comment", "key = 'value'  # This is a comment\n"),
            ("key = 'value'  # This is a comment", "key = 'value'  # This is a comment\n"),
            ("key = 'value'    # This is a comment", "key = 'value'  # This is a comment\n"),
            # Key formatting
            ("key = 'value'", "key = 'value'\n"),
            ("'key' = 'value'", "key = 'value'\n"),
            ("'key'= 'value'", "key = 'value'\n"),
            ("key.with.dots = 'value'", "[key.with]\ndots = 'value'\n"),
            # Integer formatting
            ("key = 1", "key = 1\n"),
            ("key = +1", "key = 1\n"),
            ("key= 0xab", "key = 0xAB\n"),
            # Float formatting
            ("key = 1.0", "key = 1.0\n"),
            ("key = +1.20", "key = 1.2\n"),
            ("key= 1e02", "key = 1e2\n"),
            # String formatting
            ("key = 'something'", "key = 'something'\n"),
            ('key = "something"', 'key = "something"\n'),
            # Table formatting
            ("[table]\n", "[table]\n"),
            ("[table]\nkey = 'value'\n", "[table]\nkey = 'value'\n"),
            ("[table]\n    'key' = 0xabc\n", "[table]\nkey = 0xABC\n"),
            # Array of Table formatting
            ("[[table]]\n    'key' = 0xabc\n", "[[table]]\nkey = 0xABC\n"),
            ("[[table]]\n    'key' = 0xabc\n[[table]]\nother = false\n", "[[table]]\nkey = 0xABC\n[[table]]\nother = false\n"),
            # Array formatting
            ("key = [1, 2,3]", "key = [1, 2, 3]\n"),
            ("key = [1, 2,{a = 1}]", "key = [1, 2, {a = 1}]\n"),
            # Inline Table formatting
            ("key = {inner_key = 0xa}", "key = {inner_key = 0xA}\n"),
        ),
    )
    def test_dumps(self, input_string, expected_output):
        doc = PrettyTomlDocument(input_string)
        assert doc.dumps() == expected_output


@pytest.mark.parametrize(
    ("filename", "expected_retval"),
    (
        ("invalid.toml", 1),
        ("pretty-formatted.toml", 0),
        ("not-pretty-formatted.toml", 1),
        ("not-pretty-formatted_fixed.toml", 0),
    ),
)
def test_pretty_format_toml(filename, expected_retval):
    assert pretty_format_toml([filename]) == expected_retval


@fail_because_tomlkit
def test_pretty_format_toml_autofix(tmpdir):
    run_autofix_test(
        tmpdir,
        pretty_format_toml,
        "not-pretty-formatted.toml",
        "not-pretty-formatted_fixed.toml",
    )
