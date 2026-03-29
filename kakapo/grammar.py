"""
Parsing logic for MATLAB code.
"""

# pyright: reportUnusedExpression=false


from typing import Sequence
from pathlib import Path
import itertools

from pyparsing import (
    Char,
    Combine,
    common,
    empty,
    Empty,
    Literal,
    Opt,
    Or,
    FollowedBy,
    Forward,
    ParserElement,
    PrecededBy,
    QuotedString,
    Regex,
    StringEnd,
    rest_of_line,
    White,
    Word,
    ZeroOrMore,
)

from . import model


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

# Turn-off the default behavior of ignoring whitespace. Whitespace parsing will be handled manually.
ParserElement.set_default_whitespace_chars("")


class Leaf(ParserElement):
    """Parser for the model.Leaf object. A leaf consists only af a string and does not contain child elements."""

    def __init__(self, literal: str):
        super().__init__()
        self.parser = Literal(literal)

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        assert len(tokens) == 1
        return loc, model.Literal(tokens[0])

    def _generateDefaultName(self) -> str:
        return "Leaf"


class ReservedKeyword(ParserElement):
    """A reserved keyword."""

    def __init__(self):
        super().__init__()
        self.parser = Or(Literal(s) for s in KEYWORDS)

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "ReservedKeyword"


class DelimitedList(ParserElement):
    """
    Parser for delimited list.

    Converts tokens into a model.DelimitedList object while parsing.
    """

    def __init__(
        self,
        element: ParserElement,
        delimiter: str | ParserElement,
        min_elements: int = 1,
        delimiter_is_optional: bool = False,
    ):
        super().__init__()

        if isinstance(delimiter, str):
            delimiter = Literal(delimiter)
        delimiter = ows + delimiter + ows
        if delimiter_is_optional:
            delimiter = delimiter | ws
        delimiter.add_parse_action(
            lambda s, loc, toks: model.Literal("".join(str(t) for t in toks))
        )
        min_sub_exp = max(min_elements - 1, 0)
        self.parser = (
            (
                element 
                + delimiter 
                + FollowedBy(element)
            )[min_sub_exp, ...] 
            + element
        ) # fmt: skip
        if min_elements == 0:
            self.parser = self.parser | empty

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        return loc, model.DelimitedList(list(tokens))

    def _generateDefaultName(self) -> str:
        return "DelimitedList"


class Block(ParserElement):

    def __init__(
        self,
        name: str,
        content: ParserElement,
        head: ParserElement | None = None,
        optional_head: bool = False,
        end: bool | str = True,
    ):
        super().__init__()

        end_placeholder = empty_string() + nothing()

        end_element = end_delimiter + Leaf("end")
        if isinstance(end, str):
            assert end == "optional"
            end_element |= end_placeholder
        elif not end:
            end_element = end_placeholder

        if head is None:
            head_parser = nothing(2)
        else:
            if optional_head:
                head_parser = (element_delimiter + head) | nothing(2)
            else:
                head_parser = element_delimiter + head

        content_parser = (statement_delimiter + content) | nothing(2)

        self.parser = (
            Leaf(name)
            + head_parser
            + content_parser
            + end_element
        ) # fmt: skip

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "Block"


def nothing(n: int = 1):
    return Empty().set_parse_action(
        lambda s, loc, toks: [model.Missing() for i in range(n)]
    )


def empty_string(n: int = 1):
    return Empty().set_parse_action(
        lambda s, loc, toks: [model.Literal("") for i in range(n)]
    )


def join_strings(s, loc, toks):
    return model.Literal("".join(str(t) for t in toks))


def regex_literal(pattern: str) -> ParserElement:
    return Regex(pattern).add_parse_action(model.Literal.from_tokens)


def parenthesized(
    content: ParserElement,
    brackets: Sequence[tuple[str, str]] = (("(", ")"),),
    optional: bool = False,
):
    # Turning this into a class was a lot slower for some reason
    with_parenthesis = Or(
        (
            Leaf(opening_bracket) 
            + ows 
            + content 
            + ows 
            + Leaf(closing_bracket)
        ) for opening_bracket, closing_bracket in brackets
    ) # fmt: skip

    if not optional:
        parser = with_parenthesis
    else:
        without_parenthesis = (
            nothing() + empty_string() + content + empty_string() + nothing()
        )
        parser = with_parenthesis | without_parenthesis
    return parser.add_parse_action(model.Parenthesized.from_tokens).set_name(
        "Parenthesized"
    )


"""White space including ellipsis."""
ws = Combine(
    (
        White(" \t\n") 
        | Literal("...")
    )[1, ...]
).parse_with_tabs() # fmt: skip


"""Optional white space"""
ows = (ws | empty_string()).parse_with_tabs()


element_delimiter = Combine(
    (
        White(" \t") 
        | (Literal("...") + Regex(r"[ \t]*\n?[ \t]*"))
    )[1, ...]
).parse_with_tabs() # fmt: skip


statement_delimiter = (
    ows + Leaf(";") + ows
    | regex_literal(r"[ \t]*\n") + empty_string() + ows
    | regex_literal(r"[ \t]*") + empty_string() + ows + FollowedBy(Literal("%"))
)

end_delimiter = Regex(r"[ \t\n;]+")

operator = Or(OPERATORS)


"""
A string identifying a variable, function or class. Includes namespace syntax.
Examples:
 - test123
 - a.b.c
"""
identifier_pattern = {
    "Initial": r"[A-Za-z]",
    "Body": r"[\w.]*",
    "DontEndWithDot": r"(?<!\.)",
}

identifier = (
    ~ReservedKeyword() 
    + Regex("".join(identifier_pattern.values()))
) # fmt: skip

"""A comment. Starts at the comment marker '%' end ends before the next line break."""
comment = Leaf("%") + rest_of_line.add_parse_action(model.Literal.from_tokens)


"""A quoted string with single or double quotes."""
string = (
    QuotedString(quote_char='"', esc_quote='""', unquote_results=False) | 
    QuotedString(quote_char="'", esc_quote="''", unquote_results=False)
) # fmt: skip

expression = Forward()

"""Array"""
array_delimiter = Leaf(",") | Leaf(";")
array = parenthesized(
    DelimitedList(
        expression,
        min_elements=0,
        delimiter=array_delimiter,
        delimiter_is_optional=True,
    ),
    brackets=(("[", "]"), ("{", "}")),
).set_name("Array")

call = Forward()

assignment_target = (
    parenthesized(
        DelimitedList(call, delimiter=","),
        brackets=(("[", "]"),),
        optional=True,
    )
    + ows
    + Leaf("=")
    + ows
)

assignment_statement = Forward()

argument_brackets = (("(", ")"), ("{", "}"))
argument = assignment_statement | expression | Leaf(":")
arguments_list = (
    (Leaf(".") | nothing(1))
    + parenthesized(
        DelimitedList(argument, delimiter=",", min_elements=0), 
        brackets=argument_brackets,
    )
) # fmt: skip

"""A variable or a function call with or without arguments. Includes nested calls."""
call << (
    identifier 
    + (arguments_list[1, ...] | nothing(1))
) # fmt: skip

"""
Anonymous function definition
Examples: 
 - @(x) x + 1
 - @mean
"""
anonymous_function = (
    Leaf("@") 
    + ows 
    + (arguments_list | nothing(1)) 
    + ows 
    + expression
)

# number = common.number.set_parse_action(model.Literal.from_tokens)
number = Regex(r"[-+\d][\d.eE]*").set_parse_action(model.Literal.from_tokens)

operand_atom = Forward()
operation = Forward()
operand = Forward()
operand_atom << (
    call
    | number
    | string
    | array
    | anonymous_function
    | parenthesized(operand)
    | parenthesized(operation)
)

left_operation = (Leaf("-") | Leaf("~")) + operand_atom
right_operation = operand_atom + (Leaf("'") | Leaf(".'"))

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


statement_core = expression | keyword
"""An assignment or an expression with either no result or an unused result."""

expression_statement = nothing(1) + statement_core
assignment_statement << (assignment_target + statement_core)
statement = assignment_statement | expression_statement

code = Forward()

if_ = Block(
    name="if",
    head=expression_statement,
    content=code,
    end=True,
)

else_ = Block(name="else", content=code, end=False)  # End belongs to if-block.

else_if = Block(
    name="elseif",
    head=expression_statement,
    content=code,
    end=False,  # End belongs to if-block.
)


for_ = Block(
    name="for",
    head=assignment_statement,
    content=code,
    end=True,
)
"""For-loop code block."""


while_ = Block(name="while", head=expression_statement, content=code)
"""While-loop code block."""


function = Block(name="function", head=statement, content=code, end="optional")
"""Function definition block."""


catch = Block(
    name="catch",
    head=identifier,
    optional_head=True,
    content=code,
    end=False,
)
"""'catch'-block of a try-catch block."""


try_ = Block(name="try", content=code)

switch_case = Block(name="case", head=expression_statement, content=code, end=False)
"""'case'-block of a switch statement."""


switch_otherwise = Block(name="otherwise", content=code, end=False)
"""'otherwise'-block of a switch statement."""


switch = Block(name="switch", head=expression_statement, content=code)
"""Switch statement code block"""

classdef = Block(
    name="classdef",
    head=identifier,
    content=code,
)

properties = Block(
    name="properties",
    head=arguments_list,
    content=code,
    optional_head=True,
)

methods = Block(
    name="methods",
    head=arguments_list,
    content=code,
    optional_head=True,
)

command_identifier = Combine(identifier + Opt(".*"))
command = (
    command_identifier
    + ZeroOrMore(element_delimiter + command_identifier)
    + (StringEnd() | FollowedBy(statement_delimiter))
)

any_block = (
    catch
    | classdef
    | else_
    | else_if
    | if_
    | for_
    | function
    | methods
    | properties
    | switch
    | switch_case
    | switch_otherwise
    | try_
    | while_
)


code_element = command | statement | comment | any_block
code << code_element + ZeroOrMore(statement_delimiter + code_element)


file = (
    regex_literal(r"[ \t\n;]*") 
    + (code | nothing(1)) 
    + (regex_literal(r"[ \t\n;]*") | (empty_string() + StringEnd())) # Regex fails mysteriously at string end.
)
"""A file consisting of code wrapped by optional white space."""


# Packrat gives a massive performance increase.
file.enable_packrat()

# Add parse actions to grammar objects that turn the tokens into the respective dataclass.
parse_actions = {
    anonymous_function: model.AnonymousFunction,
    array: model.Array,
    arguments_list: model.ArgumentsList,
    expression_statement: model.Statement,
    call: model.Call,
    catch: model.Catch,
    classdef: model.Classdef,
    code: model.Code,
    command: model.Command,
    command_identifier: model.Literal,
    comment: model.Comment,
    statement_delimiter: model.StatementDelimiter,
    element_delimiter: model.Literal,
    else_: model.Else,
    else_if: model.ElseIf,
    file: model.File,
    for_: model.ForLoop,
    function: model.Function,
    identifier: model.Literal,
    if_: model.If,
    methods: model.Methods,
    operation: model.Operation,
    assignment_target: model.AssignmentTarget,
    assignment_statement: model.Statement,
    properties: model.Properties,
    single_element_operation: model.SingleElementOperation,
    string: model.Literal,
    switch: model.Switch,
    switch_case: model.Case,
    switch_otherwise: model.Case,
    try_: model.Try,
    while_: model.WhileLoop,
    ws: model.Literal,
}

for parser_element, target_class in parse_actions.items():
    parser_element.add_parse_action(target_class.from_tokens)


def parse_string(s: str) -> model.File:
    """Parse a MATLAB code string and return its representation model."""
    parse_result = file.parse_string(s, parse_all=True)

    file_: model.File = parse_result[0]
    for element in itertools.chain([file_], file_.descendants()):
        if not isinstance(element, model.Composite):
            continue
        children = list(element)
        for i, child in enumerate(children):
            child.parent = element
            if i > 0:
                child.predecessor = children[i - 1]
            if i < len(children) - 1:
                child.successor = children[i + 1]

    return file_  # type: ignore


def parse_file(file_path: Path | str) -> model.File:
    """Parse a MATLAB .m file and return its representation model."""
    string = Path(file_path).read_text()
    return parse_string(string)
