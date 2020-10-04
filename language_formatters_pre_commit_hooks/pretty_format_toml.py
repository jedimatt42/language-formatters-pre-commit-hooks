# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import io
import sys
import typing

import tomlkit
from tomlkit import api
from tomlkit.container import Container
from tomlkit.exceptions import ParseError
from tomlkit.items import AoT
from tomlkit.items import Array
from tomlkit.items import Bool
from tomlkit.items import Comment
from tomlkit.items import Float
from tomlkit.items import InlineTable
from tomlkit.items import Integer
from tomlkit.items import Item
from tomlkit.items import Key
from tomlkit.items import String
from tomlkit.items import Table
from tomlkit.items import Whitespace


if getattr(typing, "TYPE_CHECKING", False):
    from tomlkit.toml_document import TOMLDocument

    T = typing.TypeVar("T")


class PrettyTomlDocument:
    @staticmethod
    def __swap_objects_inplace(obj1, obj2):
        # type: (T, T) -> None
        """
        Python trick to swap two objects without changing their memory address.
        This is needed if we want to swap the content of an object without
        having the handle of the object/variable pointing to them

        NOTE: It depends on the object having `__dict__`
        """
        obj1.__dict__, obj2.__dict__ = obj2.__dict__, obj1.__dict__

    def __init__(self, toml_content):
        # type: (typing.Text) -> None

        self.root_container = Container()
        # Ensure that the TOMLDocument (extending Container) is stored as container
        # We're doing it such that dumping allows us to sort the keys
        self.__swap_objects_inplace(self.root_container, tomlkit.parse(toml_content))

    def _prettify_array(self, value):
        # type: (Array) -> None
        # Multiline support require some tricking to ensure that is pretty.
        # We might be doing it in the future, but not for now
        value.multiline(False)
        # To prettify an array we need to have access to `_value` private attribute
        # This is needed because there is no concrete access to the internal values
        inner_values = [
            api.ws(", ") if isinstance(v, Whitespace) else self._prettify_value(v)
            for v in value._value
            if not isinstance(v, Whitespace) or v.value.strip()
        ]
        value._value = inner_values

    def _prettify_aot(self, value):
        # type: (AoT) -> None
        for container in value.value:
            self._prettify_container(container)

    def _prettify_bool(self, value):
        # type: (Bool) -> None
        pass

    def _prettify_comment(self, value):
        # type: (Comment) -> None
        value.indent(0)

    def _prettify_value(self, value):
        # type: (T) -> T
        self._prettify_indentation(value, 0)  # TODO: Enable indentation support (optional)
        self._prettify_inline_comment(value)

        if isinstance(value, AoT):
            self._prettify_aot(value)
        elif isinstance(value, Array):
            self._prettify_array(value)
        if isinstance(value, Bool):
            self._prettify_bool(value)
        elif isinstance(value, Comment):  # TODO: check later if needed
            self._prettify_comment(value)
        elif isinstance(value, InlineTable):
            self._prettify_inline_table(value)
        elif isinstance(value, Integer):
            self._prettify_integer(value)
        elif isinstance(value, Float):
            self._prettify_float(value)
        elif isinstance(value, String):
            self._prettify_string(value)
        elif isinstance(value, Table):
            self._prettify_table(value)

        if isinstance(value, (AoT, InlineTable, Table)):
            # TODO: Sort table keys
            pass

        self._prettify_trail(value)
        return value

    def _prettify_container(self, value):
        # type: (Container) -> None
        for key, value in value.body:
            if key is not None:
                self._prettify_key(key)
            if value is not None:
                self._prettify_value(value)

    def _prettify_key(self, value):
        # type: (Key) -> None
        # Create a new equivalent key via the APIs
        # Doing it enables us to create the key as we like instead of being
        # dependend on how it looked in the input
        # The preference would be to have bare keys (no quotes) whenever possible
        self.__swap_objects_inplace(value, api.key(value.key.strip()))

    def _prettify_indentation(self, value, indent_level):
        # type: (Item, int) -> None
        # Indent the item to the defined level
        if isinstance(value, Whitespace):
            return

        value.indent(indent_level)

    def _prettify_inline_table(self, value):
        # type: (InlineTable) -> None
        self._prettify_container(value.value)

    def _prettify_inline_comment(self, value):
        # type: (Item) -> None
        if isinstance(value, Whitespace):
            return

        if not value.trivia.comment:
            return

        # Ensure that a comment will always start with `# `
        comment_string = value.trivia.comment.lstrip("#").strip()
        value.comment(comment_string)
        # An inline comment will have 2 leading spaces (to separe the value from the comment)
        value.trivia.comment_ws = "  "

    def _prettify_integer(self, value):
        # type: (Integer) -> None
        str_value = value.as_string()

        is_zero = value == 0
        is_binary = str_value.startswith("0b")
        is_octal = str_value.startswith("0o")
        is_hexadecimal = str_value.startswith("0x")

        # Remove separators
        str_value = str_value.replace("_", "")

        if str_value.startswith("+"):
            # Leading '+' does not provide information, removing it
            str_value = str_value[1:]

        if is_hexadecimal:
            # We're dealing with hexadecimal numbers, let's ensure a common format
            str_value = "0x{}".format(str_value[2:].upper())

        if (is_binary or is_octal or is_hexadecimal) and str_value[2] == "0":
            # The number has leading 0s, we're removing them
            str_value = "{}{}".format(str_value[:2], str_value[2:].lstrip("0"))

        if is_zero:
            str_value = "0"

        # Sadly we don't have and API that allows to craeate an integer with a given format
        # So we go through the parser
        new_value = tomlkit.parse("key = {}".format(str_value))["key"]
        self.__swap_objects_inplace(value, new_value)

    def _prettify_float(self, value):
        # type: (Float) -> None
        str_value = value.as_string()

        is_zero = value == 0.0
        is_exponential = "e" in str_value or "E" in str_value
        has_trailing_zeros = str_value.endswith("0")

        # Remove separators
        str_value = str_value.replace("_", "")

        if str_value.startswith("+"):
            # Leading '+' does not provide information, removing it
            str_value = str_value[1:]

        if is_exponential:
            # We're dealing with exponential format, let's ensure a common format
            str_value = str_value.lower()

            if "e0" in str_value:
                # The exponent has leading 0s
                number, exponent = str_value.split("e")
                str_value = "{}e{}".format(number, int(exponent))

        if has_trailing_zeros:
            # The number has trailing 0s, we're removing them while preserving the first
            str_value = str_value.rstrip("0")
            if str_value.endswith("."):
                # A number as "1." is not valid, so adding a traling 0
                str_value = "{}0".format(str_value)

        if is_zero:
            str_value = "0.0"

        # Sadly we don't have and API that allows to craeate an integer with a given format
        # So we go through the parser
        new_value = tomlkit.parse("key = {}".format(str_value))["key"]
        self.__swap_objects_inplace(value, new_value)

    def _prettify_string(self, value):
        # type: (String) -> None
        pass

    def _prettify_table(self, value):
        # type: (Table) -> None
        self._prettify_container(value.value)

    def _prettify_trail(self, value):
        # type: (Item) -> None
        if isinstance(value, Whitespace):
            return
        value.trivia.trail = "\n"

    def prettify(self):
        # type: () -> None
        self._prettify_container(self.root_container)

    def dumps(self):
        # type: () -> str
        self.prettify()
        return self.root_container.as_string()  # type: ignore  # for some reason mypy does not recognise the correct return type  # noqa: E501


def pretty_format_toml(argv=None):
    # type: (typing.Optional[typing.List[typing.Text]]) -> int
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--autofix",
        action="store_true",
        dest="autofix",
        help="Automatically fixes encountered not-pretty-formatted files",
    )
    parser.add_argument("filenames", nargs="*", help="Filenames to fix")
    args = parser.parse_args(argv)

    status = 0

    for toml_file in set(args.filenames):
        with open(toml_file) as input_file:
            string_content = "".join(input_file.readlines())

        try:
            pretty_toml_doc = PrettyTomlDocument(toml_content=string_content)
        except ParseError as error:
            print("Input File {} is not a valid TOML file".format(toml_file))
            print(error, file=sys.stderr)
            status = 1
            continue

        prettified_content = pretty_toml_doc.dumps()

        if string_content != prettified_content:
            print("File {} is not pretty-formatted".format(toml_file))

            if args.autofix:
                print("Fixing file {}".format(toml_file))
                with io.open(toml_file, "w", encoding="UTF-8") as output_file:
                    output_file.write(prettified_content)

            status = 1

    return status


if __name__ == "__main__":
    sys.exit(pretty_format_toml())
