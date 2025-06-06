from typing import Sequence
from pathlib import Path

from pyparsing import (
    Char,
    Combine,
    common,
    empty,
    Empty,
    line_end,
    Literal,
    Opt,
    Or,
    FollowedBy,
    Forward,
    ParserElement,
    PrecededBy,
    QuotedString,
    Regex,
    rest_of_line,
    White,
    Word,
    ZeroOrMore,
)

import model


OPERATORS = [
    "+",
    "-",
    "*",
    ".*",
    "/",
    "./",
    "^",
    ".^",
    "\\",
    "==",
    "~=",
    ">",
    ">=",
    "<",
    "<=",
    "&",
    "&&",
    "|",
    "||",
    ":",
]

KEYWORDS = [
    "arguments",
    "break",
    "case",
    "catch",
    "classdef",
    "continue",
    "else",
    "elseif",
    "end",
    "for",
    "function",
    "global",
    "if",
    "methods",
    "otherwise",
    "parfor",
    "persistent",
    "properties",
    "return",
    "spmd",
    "switch",
    "try",
    "while",
]


ParserElement.setDefaultWhitespaceChars("")


def nothing(n: int = 1):
    return Empty().set_parse_action(lambda s, loc, toks: ["" for i in range(n)])


def or_none(expr: ParserElement):
    """Parse expr or return None if not found."""
    return Opt(expr, default=None)


class ReservedKeyword(ParserElement):
    """A reserved keyword."""

    def __init__(self):
        super().__init__()
        self.parser = Or(Literal(s) for s in KEYWORDS)

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "ReservedKeyword"


"""White space including ellipsis."""
ws = Combine((White(" \t\n") | Literal("..."))[1, ...]).parse_with_tabs()

"""Optional white space"""
ows = Opt(ws, default="").parse_with_tabs()

operator = Or(OPERATORS)


class Leaf(ParserElement):

    def __init__(self, literal: str):
        super().__init__()
        self.parser = Literal(literal)

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        assert len(tokens) == 1
        return loc, model.Leaf(tokens[0])

    def _generateDefaultName(self) -> str:
        return "Leaf"


class DelimitedList(ParserElement):
    """
    Parser for delimited list.

    Converts tokens into a model.DelimitedList object while parsing.
    """

    def __init__(
        self,
        expr: ParserElement,
        delimiter: str | ParserElement = ",",
        min_elements: int = 1,
        optional_delimiter: bool = False,
    ):
        super().__init__()

        if isinstance(delimiter, str):
            delimiter = Literal(delimiter)
        delimiter = ows + delimiter + ows
        if optional_delimiter:
            delimiter = delimiter | ws
        delimiter.add_parse_action(lambda s, loc, toks: ["".join(toks)])
        self.parser = (expr + delimiter + FollowedBy(expr))[
            max(min_elements - 1, 0), ...
        ] + expr
        if min_elements == 0:
            self.parser = self.parser | empty

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        return loc, model.DelimitedList(tokens)

    def _generateDefaultName(self) -> str:
        return "DelimitedList"


class Block(ParserElement):
    def __init__(
        self,
        name: str,
        content: ParserElement,
        head: ParserElement | None = None,
        end: bool | str = True,
    ):
        # Make sure content and head are parsed as a single token.

        super().__init__()

        head = head if head else nothing()

        end_element = (
            ws
            + Leaf("end")
            + Opt(ows + Literal(";"), default=None).add_parse_action(
                lambda toks: ["", ""] if toks[0] is None else toks
            )
        )
        if isinstance(end, str):
            assert end == "optional"
            end_element |= nothing(2)
        elif not end:
            end_element = nothing(2)

        self.parser = Literal(name) + ws + head + ows + content + end_element

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "Block"


def space_delimited_list(
    expr: ParserElement, allow_empty: bool = False
) -> ParserElement:
    result = ZeroOrMore(expr + ws + FollowedBy(expr)) + expr
    if allow_empty:
        result = result | empty
    return result


def ows_delimited_list(expr: ParserElement, allow_empty: bool = False) -> ParserElement:
    result = ZeroOrMore(expr + construct_delimiter + FollowedBy(expr)) + expr
    if allow_empty:
        result = result | empty
    return result


def parenthesized(
    content: ParserElement,
    brackets: Sequence[tuple[str, str]] = (("(", ")"),),
    optional: bool = False,
):
    # Turning this into a class was a lot slower for some reason
    with_parenthesis = Or(
        (opening_bracket + ows + content + ows + closing_bracket)
        for opening_bracket, closing_bracket in brackets
    )
    if not optional:
        parser = with_parenthesis
    else:
        without_parenthesis = nothing(2) + content + nothing(2)
        parser = with_parenthesis | without_parenthesis
    return parser.add_parse_action(model.Parenthesized.from_tokens).set_name(
        "Parenthesized"
    )


"""
A string identifying a variable, function or class. Includes namespace syntax.
Examples:
 - test123
 - a.b.c
"""
keyword_pattern = {
    "Initial": r"[A-Za-z]",
    "Body": r"[\w.]*",
    "DontEndWithDot": r"(?<!\.)",
}

identifier = ~ReservedKeyword() + Regex("".join(keyword_pattern.values()))

"""A comment. Starts at the comment marker '%' end ends at the next line break."""
comment = Literal("%") + rest_of_line


construct_delimiter = Combine(
    (PrecededBy(";") + Word(" \t\n"))
    | Opt(Word(" \t"), default="") + Char("\n") + Opt(Word(" \t\n"), default="")
    | Opt(Word(" \t"), default="") + FollowedBy(comment)
    | line_end
)


"""A quoted string with single or double quotes."""
string = QuotedString(
    quote_char='"', esc_quote='""', unquote_results=False
) | QuotedString(quote_char="'", esc_quote="''", unquote_results=False)

expression = Forward()

"""Array"""
array_delimiter = Literal(",") | Literal(";")
array = parenthesized(
    DelimitedList(
        expression, min_elements=0, delimiter=array_delimiter, optional_delimiter=True
    ),
    brackets=(("[", "]"), ("{", "}")),
).set_name("Array")

call = Forward()

output_arguments = (
    parenthesized(
        DelimitedList(call),
        brackets=(("[", "]"),),
        optional=True,
    )
    + ows
    + Literal("=")
    + ows
)


argument_brackets = (("(", ")"), ("{", "}"))
arguments_list = Opt(Literal("."), default="") + parenthesized(
    DelimitedList(expression | Literal(":"), min_elements=0), brackets=argument_brackets
)

"""A variable or a function call with or without arguments. Includes nested calls."""
call << (identifier + or_none(arguments_list[1, ...]))

"""
Anonymous function definition
Examples: 
 - @(x) x + 1
 - @mean
"""
anonymous_function = Literal("@") + ows + or_none(arguments_list) + ows + expression


operand_atom = Forward()
operation = Forward()
operand = Forward()
operand_atom << (
    call
    | common.number
    | string
    | array
    | anonymous_function
    | parenthesized(operand)
    | parenthesized(operation)
)

left_operation = (Literal("-") | Literal("~")) + operand_atom
right_operation = operand_atom + (Literal("'") | Literal(".'"))

single_element_operation = left_operation | right_operation

operand << (
    single_element_operation
    | operand_atom
    | parenthesized(operand)
    | parenthesized(operation)
)
operation << DelimitedList(operand, delimiter=operator, min_elements=2)
expression << (operation | operand)

keyword = Or(Leaf(kw) for kw in ["return", "break", "continue"])

"""An assignment or an expression with either no result or an unused result."""

statement_core = (
    (expression | keyword)
    + Opt(ows + FollowedBy(Literal(";")), default="")
    + Opt(Literal(";"), default="")
)

no_output_statement = nothing(1) + statement_core
output_statement = output_arguments + statement_core
statement = output_statement | no_output_statement

code = Forward()

elseif_block_part = Leaf("elseif") + ws + no_output_statement + ws + code

else_block_part = Leaf("else") + ws + code

"""If block including possible "elseif" and "else" subblocks."""
if_block = Block(
    name="if",
    head=no_output_statement,
    content=(code + ZeroOrMore(ws + elseif_block_part) + Opt(ws + else_block_part)),
    end=True,
)

"""For-loop code block."""
for_loop = Block(
    name="for",
    head=output_statement,
    content=code,
    end=True,
)

"""While-loop code block."""
while_loop = Block(name="while", head=no_output_statement, content=code)

"""Function definition block."""
function = Block(name="function", head=statement, content=code, end="optional")

catch = (
    Literal("catch")
    + Opt(White(" \t") + statement_core, default=None).add_parse_action(
        lambda toks: ["", ""] if toks[0] is None else toks
    )
    + ws
    + code
)

try_catch = Block(name="try", content=(code + or_none(ws + catch)))

switch_case = Block(name="case", head=no_output_statement, content=code, end=False)

switch_otherwise = Block(name="otherwise", content=code, end=False)

switch = Block(
    name="switch",
    head=no_output_statement,
    content=ows_delimited_list(switch_case | switch_otherwise, allow_empty=True),
)

classdef = Block(
    name="classdef",
    head=identifier,
    content=code,
)

methods = Block(
    name="methods",
    content=code,
)

command_identifier = Combine(identifier + Opt(".*"))
command = space_delimited_list(command_identifier) + FollowedBy(construct_delimiter)

any_block = (
    if_block
    | for_loop
    | while_loop
    | function
    | try_catch
    | switch
    | classdef
    | methods
)

code << ows_delimited_list(command | statement | comment | any_block, allow_empty=True)

file = ows + code + ows
file.enablePackrat()

# Add parse actions to grammar objects which turn the tokens into the respective dataclass.
parse_actions = {
    arguments_list: model.ArgumentsList,
    function: model.Function,
    if_block: model.If,
    try_catch: model.TryCatch,
    for_loop: model.ForLoop,
    while_loop: model.WhileLoop,
    call: model.Call,
    output_arguments: model.OutputArguments,
    comment: model.Comment,
    operation: model.Operation,
    no_output_statement: model.Statement,
    output_statement: model.Statement,
    code: model.Code,
    anonymous_function: model.AnonymousFunction,
    array: model.Array,
    single_element_operation: model.SingleElementOperation,
    file: model.File,
    switch: model.Switch,
    switch_case: model.Case,
    switch_otherwise: model.Case,
    command: model.Command,
    classdef: model.Classdef,
    methods: model.Methods,
}

for parser_element, target_class in parse_actions.items():
    parser_element.add_parse_action(target_class.from_tokens)


def parse_string(s: str) -> model.File:
    """Parse a MATLAB code string and return its representation model."""
    parse_result = file.parse_string(s, parse_all=True)
    return parse_result[0]


def parse_file(file_path: Path | str) -> model.File:
    """Parse a MATLAB .m file and return its representation model."""
    parse_result = file.parse_file(str(file_path), parse_all=True)
    return parse_result[0]
