from __future__ import annotations
from dataclasses import KW_ONLY, dataclass, field, fields
import re
from typing import Generator, Sequence, Any, Type


@dataclass
class Component:
    """Base class for all code elements."""

    _: KW_ONLY
    _parent: Composite | None = field(default=None, repr=False)
    _successor: Component | None = field(default=None, repr=False)
    _predecessor: Component | None = field(default=None, repr=False)

    @property
    def parent(self) -> Composite | None:
        return self._parent
    
    @parent.setter
    def parent(self, parent: Composite | None):
        self._parent = parent

    @property
    def successor(self) -> Component | None:
        return self._successor
    
    @successor.setter
    def successor(self, successor: Component | None):
        self._successor = successor

    @property
    def predecessor(self) -> Component | None:
        return self._predecessor

    @predecessor.setter
    def predecessor(self, predecessor: Component | None):
        self._predecessor = predecessor


@dataclass
class Literal(Component):
    """Leaf with literal value."""

    value: str

    def regex_replace(self, pattern: str, repl: str):
        self.value = re.sub(pattern=pattern, repl=repl, string=self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}({self.value!r})"

    def __eq__(self, other: Literal | str) -> bool:
        if isinstance(other, str):
            return self.value == other
        return self.value == other.value

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        assert len(tokens) == 1
        return cls(tokens[0])
    

@dataclass
class Missing(Component):
    """Leaf representing a missing optional element."""
    
    def __str__(self) -> str:
        return ""
    

@dataclass
class Composite(Component):

    _NON_CHILD_FIELDS = {"_parent", "_successor", "_predecessor"}

    def __iter__(self):
        for name in self.__dataclass_fields__:
            if name not in self._NON_CHILD_FIELDS:
                yield getattr(self, name)

    def descendants(self) -> Generator[Component]:
        for child in self:
            yield child
            if isinstance(child, Composite):
                for grand_child in child.descendants():
                    yield grand_child

    def __str__(self) -> str:
        strings = [str(child) for child in self]
        return "".join(strings)

    def __len__(self) -> int:
        return len(fields(self))

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"{name}({list(self)})"

    def __eq__(self, other) -> bool:
        """Elements are equal if they have equal type and their children are equal."""
        if type(self) is not type(other) or len(self) != len(other):
            return False
        return all(
            own_child == other_child for own_child, other_child in zip(self, other)
        )

    def descendants_and_indent(self, level: int = 0) -> Generator[tuple[Component, int]]:
        for child in self:
            if isinstance(child, (Else, ElseIf, Catch)):
                level -= 1
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.descendants_and_indent(level):
                    yield grand_child, grand_child_level
            if isinstance(child, (Else, ElseIf, Catch)):
                level += 1

    def pretty_string(
        self,
        indent_level: int = 0,
        compact: bool = False,
        nested: bool = True,
    ) -> str:
        indent = indent_level * 4 * " "
        type_ = self.__class__.__name__

        head = f"{type_}(["
        tail = "])"

        if all(not isinstance(child, Composite) for child in self):
            body = ", ".join(repr(child) for child in self)
            return indent + head + body + tail

        body_parts = []
        for child in self:
            if isinstance(child, Composite):
                if nested:
                    body_part = child.pretty_string(indent_level + 1, compact)
                else:
                    body_part = f"{indent}    {child.__class__.__name__}(...)"
            else:
                if compact and none_or_whitespace(child):
                    continue
                body_part = f"{indent}    {child!r},"
            body_parts.append(body_part)
        body = "\n".join(body_parts)
        return f"{indent}{head}\n{body}\n{indent}{tail}"

    def to_list(self) -> list:
        return [c.to_list() if isinstance(c, Composite) else c for c in self]

    def to_repr_list(self) -> list:
        return [c.to_repr_list() if isinstance(c, Composite) else c for c in self]

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        return cls(*tokens)


class Construct:
    """A code element which can stand on its own: Statements, Blocks and Comments."""


class ElementsList(Composite):

    @property
    def elements_list(self) -> DelimitedList:
        raise NotImplementedError()

    @property
    def elements(self) -> Sequence:
        raise NotImplementedError


@dataclass
class ArgumentsList(Composite):
    dot: Literal
    parenthesized: Parenthesized


@dataclass
class AssignmentTarget(Composite):
    elements_list: DelimitedList
    whitespace_before_equal_sign: Literal
    equal_sign: Literal
    whitespace_after_equal_sign: Literal


@dataclass
class Call(Composite):
    identifer: Literal
    arguments_list: ArgumentsList | Missing

    @property
    def arguments(self) -> Sequence:
        if isinstance(self.arguments_list, Missing):
            return tuple()
        return self.arguments_list.elements


@dataclass
class Comment(Composite, Construct):
    marker: Literal
    content: Literal


@dataclass
class Operation(Composite):
    delimited_list: DelimitedList


@dataclass
class Parenthesized(Composite):
    opening_delimiter: Literal
    whitespace_before_content: Literal
    content: Component
    whitespace_after_content: Literal
    closing_delimiter: Literal


@dataclass
class Statement(Composite, Construct):
    output_arguments: AssignmentTarget | Missing
    body: Component


@dataclass(eq=False)
class VariableLengthComposite(Composite):
    children: list[Component]

    def __iter__(self):
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __getitem__(self, key):
        return self.children[key]

    def __setitem__(self, key, value):
        self.children[key] = value

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        return cls(list(tokens))


class Code(VariableLengthComposite):
    pass


class DelimitedList(VariableLengthComposite):

    @property
    def elements(self) -> list:
        return self.children[::2]


@dataclass
class Block(Composite, Construct):
    name: Literal
    pre_head_delimiter: Literal
    head: Component | Missing
    pre_body_delimiter: Literal
    body: Component
    pre_end_delimiter: Literal
    end: Literal | Missing

    def descendants_and_indent(self, level: int = 0) -> Generator[tuple[Component, int]]:
        for i, child in enumerate(self):
            if i == 4:
                level += 1
            if i == 5:
                level -= 1
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.descendants_and_indent(level):
                    yield grand_child, grand_child_level



class Function(Block):
    pass


class Class(Block):
    pass


class Properties(Block):
    pass


class Methods(Block):
    pass


class If(Block):
    pass

class ForLoop(Block):
    pass


class WhileLoop(Block):
    pass


class Try(Block):
    pass


class Catch(Block):
    pass


class Switch(Block):
    pass


class Case(Block):
    pass


class Otherwise(Block):
    pass


@dataclass
class File(Composite):
    leading_delimiter: Literal
    code: Code
    trailing_delimiter: Literal


@dataclass
class AnonymousFunction(Composite):
    at_sign: Literal
    white_space_before_arguments: Literal
    arguments_list: DelimitedList
    white_space_after_arguments: Literal
    expression: Component

    @property
    def arguments(self) -> list:
        return self.arguments_list.elements


@dataclass
class Array(Composite):
    parenthesized: Parenthesized


@dataclass
class PrefixOperation(Composite):
    operator: Literal
    operand: Component


@dataclass
class PostfixOperation(Composite):
    operand: Component
    operator: Literal


@dataclass(eq=False)
class Command(VariableLengthComposite, Construct):
    pass


class Classdef(Block):
    pass


class Else(Block):
    pass


class ElseIf(Block):
    pass


@dataclass
class ArgumentDefinition(Composite):
    name: Literal
    pre_shape_delimiter: Literal
    shape: ArgumentsList
    pre_type_delimiter: Literal
    type: Literal


class ArgumentDefinitionGroup(VariableLengthComposite):
    pass


def none_or_whitespace(x) -> bool:
    return x is None or isinstance(x, str) and (x.isspace() or x == "")
