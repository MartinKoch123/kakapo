from pathlib import Path
from unittest import case
import re

import pyparsing

from . import model, grammar
from .model import Literal


INDENT = 4 * " "


def format_type(type_: type[model.Component]):
    def decorator(func):
        def wrapper(code: model.Composite):
            for element in code.descendants():
                if isinstance(element, type_):
                    func(element)

        return wrapper

    return decorator


@format_type(model.DelimitedList)
def normalize_whitespace_in_delimited_list(delimited_list: model.DelimitedList):
    for i, element in enumerate(delimited_list):
        # Children 1, 3, ... are whitespace and delimiters.
        if i % 2 == 0:
            continue
        assert isinstance(element, model.Literal)
        string = element.value
        string = string.strip(" \n\t")  # Remove whitespace surrounding delimiter
        string = string.replace("...", "")  # Remove ellipsis
        string += " "  # Add single space after delimiter.
        if not any(char in string for char in ",;"):
            string = " " + string
        element.value = string


@format_type(model.Parenthesized)
def normalize_whitespace_in_parenthesized(parenthesized: model.Parenthesized):
    parenthesized.whitespace_before_content = Literal("")
    parenthesized.whitespace_after_content = Literal("")


@format_type(model.AssignmentTarget)
def normalize_whitespace_in_assignment(output_arguments: model.AssignmentTarget):
    """Ensure equality sign of assignment is surrounded by single spaces."""
    output_arguments.whitespace_before_equal_sign = Literal(" ")
    output_arguments.whitespace_after_equal_sign = Literal(" ")


@format_type(model.Block)
def remove_post_block_whitespace_and_semicolon(block: model.Block):
    if not isinstance(block.successor, model.Literal):
        return
    block.successor.regex_replace(pattern=r"^(\s*;+)+", repl="")


@format_type(model.Block)
def remove_post_block_head_whitespace_and_semicolon(block: model.Block):
    block.pre_body_delimiter.regex_replace(pattern=r"^(\s*;+)+", repl="")


def remove_white_space_and_semicolon_after_keyword(code: model.Composite):
    for element in code.descendants():
        match element:
            case model.Literal(
                predecessor=model.Statement(
                    body=Literal(value="return" | "break" | "continue")
                )
            ):
                element.regex_replace(pattern=r"^(\s*;+)+", repl="")

                # Ensure delimiter contains at least one space.
                if element.value == "":
                    element.value = " "


@format_type(model.Literal)
def remove_white_space_before_semicolon(literal: model.Literal):
    literal.regex_replace(pattern=r"^[\s;]+;", repl=";")


@format_type(model.Function)
def ensure_function_end(function: model.Function):
    """Ensure function block ends with 'end' keyword."""
    if function.pre_end_delimiter == Literal(""):
        function.pre_end_delimiter = Literal("\n")
    function.end = Literal("end")


def normalize_trailing_whitespace(file: model.File):
    """Remove all trailing whitespace in a file and add a newline."""
    new_value = "\n"
    if ";" in file.trailing_delimiter.value:
        new_value = ";" + new_value
    file.trailing_delimiter.value = new_value


def normalize_leading_whitespace(file: model.File):
    """Remove all leading whitespace in a file."""
    file.leading_delimiter.value = ""


@format_type(model.Comment)
def ensure_comment_leading_space(comment: model.Comment):
    """Ensure there is a single space after the comment marker if the comment is not empty."""
    if not comment.content.value.startswith(" "):
        comment.content = Literal(" " + comment.content.value)


@format_type(model.Code)
def ensure_empty_line_before_comment(code: model.Code):
    """Ensures an empty line before each block of comments."""
    for i, child in enumerate(code.children):

        if not isinstance(child, model.Comment):
            continue

        if child.predecessor is None:
            continue
        predecessor = child.predecessor

        if predecessor.predecessor is None or isinstance(
            predecessor.predecessor, model.Comment
        ):
            continue

        assert type(predecessor) is model.Literal

        # Inline comment, or already has an empty line before it.
        if predecessor.value.count("\n") != 1:
            continue
        if ";" in predecessor.value:

            # Add newline after last semicolon.
            predecessor.regex_replace(r";(?=[^;]*$)", ";\n")
        else:
            predecessor.value = "\n" + predecessor.value


def normalize_indentation(composite: model.Composite):

    for element, level in composite.descendants_and_indent():

        if (
            not isinstance(element, model.Construct)
            and (not isinstance(element, model.Literal) or element.value != "end")
        ):
            continue
        # if isinstance(element, model.Comment):
        #     continue

        parent = element.parent
        predecessor = element.predecessor

        element_is_block_head = (
            parent
            and isinstance(parent, model.Block)
            and type(parent.head) is type(element)
            and parent.head == element
        )
        if element_is_block_head:
            continue

        assert level >= 0
        indent = level * INDENT

        if not predecessor and not parent:
            continue

        if predecessor:
            preceeding_literal = predecessor
        else:
            preceeding_literal = parent.predecessor

        # Predecessor should be whitespace and semicolons.
        assert isinstance(preceeding_literal, model.Literal)

        string = preceeding_literal.value
        assert re.match(pattern=r"( \n;)*", string=string)

        # Skip inline comments.
        if isinstance(element, model.Comment) and "\n" not in string:
            continue

        # Remove current indentation (to be added later).
        string = string.rstrip(" ")

        # Ensure there is a newline at the end of the whitespace, so that the current
        # element is on a new line (unless it's a comment).
        if preceeding_literal.predecessor and "\n" not in string:
            string += "\n"

        # Add normalized indentation.
        preceeding_literal.value = string + indent


@format_type(model.Literal)
def remove_excess_empty_lines(literal: model.Literal):
    literal.regex_replace(pattern=r"\n\s*\n", repl=r"\n\n")


@format_type(model.Literal)
def add_empty_lines_before_and_after_blocks(literal: model.Literal):
    match literal:
        case model.Literal(
            predecessor=model.Block(
                name=model.Literal("classdef" | "function" | "methods" | "properties" | "arguments")
            )
        ):
            while literal.value.count("\n") < 2:
                literal.value += "\n"
        case model.Literal(
            successor=model.Block(
                name=model.Literal("classdef" | "function" | "methods" | "properties" | "arguments")
            )
        ):
            while literal.value.count("\n") < 2:
                literal.value += "\n"


@format_type(model.Block)
def add_empty_lines_around_block_body(block: model.Block):
    if block.name not in ["classdef", "methods"]:
        return
    for delimiter in (block.pre_body_delimiter, block.pre_end_delimiter):
        while delimiter.value.count("\n") < 2:
            delimiter.value += "\n"


# def break_arguments(element: model.Composite, max_line_length: int = 120):
#     for descendant, level in element.descendants_and_indent():

#         if not isinstance(descendant, model.Statement):
#             continue

#         outer_indent = level * INDENT
#         inner_indent = (level + 1) * INDENT

#         line_length = len(str(descendant) + inner_indent)
#         if line_length <= max_line_length:
#             continue

#         body = descendant.body
#         if not isinstance(body, model.Call):
#             continue

#         args_list = body.arguments_list
#         if isinstance(args_list, model.Missing):
#             continue

#         args_list[1][1] = " ...\n" + inner_indent

#         for i, token in enumerate(args_list.elements_list):
#             if i % 2 == 0:
#                 continue

#             args_list.elements_list[i] = ", ...\n" + inner_indent

#         args_list[1][3] = " ...\n" + outer_indent


def format_model(file: model.File):
    normalize_whitespace_in_delimited_list(file)
    normalize_whitespace_in_parenthesized(file)
    normalize_whitespace_in_assignment(file)
    remove_post_block_whitespace_and_semicolon(file)
    remove_post_block_head_whitespace_and_semicolon(file)
    remove_white_space_before_semicolon(file)
    remove_white_space_and_semicolon_after_keyword(file)
    remove_excess_empty_lines(file)
    add_empty_lines_before_and_after_blocks(file)
    add_empty_lines_around_block_body(file)
    normalize_indentation(file)
    ensure_function_end(file)
    normalize_leading_whitespace(file)
    normalize_trailing_whitespace(file)
    ensure_empty_line_before_comment(file)
    ensure_comment_leading_space(file)
    # break_arguments(file)


def format_string(string: str):
    file_model = grammar.parse_string(string)
    format_model(file_model)
    # normalize_indentation(file_model)
    return str(file_model)


def format_file(file_path: Path):
    string = file_path.read_text()
    string = format_string(string)
    file_path.write_text(string)
