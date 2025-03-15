from typing import Sequence
from dataclasses import dataclass
from abc import ABC, abstractmethod

import pyparsing as pp
from pyparsing import Literal, Suppress, White, Opt, ParserElement, Or, Word, alphas, alphanums, DelimitedList
from pyparsing import Group, rest_of_line, ZeroOrMore, OneOrMore, Regex, empty, FollowedBy, common

ParserElement.setDefaultWhitespaceChars('')


class Element:

    def __init__(self, tokens: Sequence):
        self.children = tokens

    def __iter__(self):
        return iter(self.children)

    def __str__(self):
        return "".join(str(tok) for tok in self)

    def pretty_string(self):
        lines = [self.__class__.__name__ + '(children=[']

        for child in self:
            if isinstance(child, Element):
                lines += child.pretty_string().split('\n')
            elif isinstance(child, str):
                lines += [repr(child) + ","]
        if all(isinstance(child, str) for child in self):
            line = " ".join(line for line in lines) + "]"
            return "" + line
        else:
            return '\n    '.join(lines) + "\n]"

    def to_list(self) -> list:
        return [c.to_list() if isinstance(c, Element) else c for c in self]

    def to_repr_list(self) -> list:
        return [c.to_repr_list() if isinstance(c, Element) else c for c in self]


    @classmethod
    def from_tokens(cls, tokens: Sequence):
        return cls(list(tokens))

class ArgumentsList(Element):
    pass

class OutputArgumentList(Element):
    pass

class FunctionCall(Element):
    pass

class Function(Element):
    pass

class Comment(Element):
    pass

class Operation(Element):
    pass

class Statement(Element):
    pass

class Code(Element):
    pass


RESERVED_KEYWORDS = [
    "arguments", "end", "if", "classdef", "switch", "case", "for", "while", "function", "else", "elseif", "break",
    "continue", "return"
]

ws = White(" \t\n").parse_with_tabs()
ows = Opt(ws, default="")


def ignore(literal: str):
    return Suppress(Literal(literal))


def delimited_list(expr: ParserElement, delim: str | ParserElement, allow_empty: bool = False) -> ParserElement:
    if isinstance(delim, str):
        delim = Literal(delim)
    result = ZeroOrMore(expr + ows + delim + ows + FollowedBy(expr)) + expr
    if allow_empty:
        result = result | empty
    return result


def space_delimited_list(expr: ParserElement, allow_empty: bool = False) -> ParserElement:
    result = ZeroOrMore(expr + ws + FollowedBy(expr)) + expr
    if allow_empty:
        result = result | empty
    return result


def group(expr: ParserElement):
    return Group(expr, aslist=True)


reserved_keywords = Or(Literal(s) for s in RESERVED_KEYWORDS)

name = ~reserved_keywords + Word(alphas, alphanums + "_", max=63, min=1)

comment = Literal("%") + rest_of_line


def parenthesized(content: ParserElement, chars: Sequence[str] = "()", optional: bool = False):
    result = chars[0] + content + chars[1]
    if optional:
        result = result | content
    return result


arguments_list = parenthesized(delimited_list(name, delim=","))

output_arguments = (
    parenthesized(
        DelimitedList(
            ows + name + ows,
            delim=","
        ),
        chars="[]",
        optional=True,
    )
    + ows + Literal("=") + ows
)

function_call = name + arguments_list

expression = name | common.number

operation = delimited_list(expression, delim=Word("+-*/."))

statement = (
    Opt(output_arguments, default=None)
    + (operation)
    + ows + Opt(Literal(";"), default="")
)

code = space_delimited_list(statement | comment, allow_empty=False)

function = (
    Literal("function") + ws
    + Opt(output_arguments, default=None)
    + function_call + ws
    + code
    # + ws + "end"
)

parse_actions = {
    arguments_list: ArgumentsList,
    function: Function,
    function_call: FunctionCall,
    output_arguments: OutputArgumentList,
    comment: Comment,
    operation: Operation,
    statement: Statement,
    code: Code,
}

for parser_element, target_class in parse_actions.items():
    parser_element.add_parse_action(target_class.from_tokens)