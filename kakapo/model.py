from __future__ import annotations
from dataclasses import KW_ONLY, dataclass, field, fields
from abc import ABC, abstractmethod
from typing import Generator, Sequence, Any, Type


@dataclass
class Component(ABC):
    """Base class for all code elements."""

    _: KW_ONLY
    parent: Composite | None = field(default=None, repr=False)
    _successor: Component | None = field(default=None, repr=False)
    _predecessor: Component | None = field(default=None, repr=False)

    @property
    def successor(self) -> Component | None:
        return self._successor

    @property
    def predecessor(self) -> Component | None:
        return self._predecessor

    def __iter__(self):
        return iter(())

    def iterate(self):
        return iter(())

    def iterate_with_indent(self, level: int = 0) -> Generator[tuple[Component, int]]:
        raise NotImplementedError()

    def __len__(self) -> int:
        return 1

    @abstractmethod
    def __str__(self) -> str:
        """Convert the code model to a code string."""


@dataclass
class Leaf(Component):
    """Component with no children."""

    value: str | None

    def __str__(self) -> str:
        if self.value is None:
            return ""
        return str(self.value)

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}({self.value!r})"

    def __eq__(self, other: Leaf | str | None) -> bool:
        if isinstance(other, (str | None)):
            return self.value == other
        return self.value == other.value

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        assert len(tokens) == 1
        return cls(tokens[0])


@dataclass
class Composite(Component):

    _NON_CHILD_FIELDS = {"parent", "_successor", "_predecessor"}

    def __iter__(self):
        for name in self.__dataclass_fields__:
            if name not in self._NON_CHILD_FIELDS:
                yield getattr(self, name)

    def iterate(self) -> Generator[Component]:
        for child in self:
            yield child
            if isinstance(child, Composite):
                for grand_child in child.iterate():
                    yield grand_child

    def __str__(self) -> str:
        strings = [str(child) for child in self if child is not None]
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

    def index_of_child(self, child: Component) -> int:
        for i, other in enumerate(self):
            if child is other:
                return i
        raise ValueError("Child not found.")

    def iterate_with_indent(self, level: int = 0) -> Generator[tuple[Component, int]]:
        for child in self:
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.iterate_with_indent(level):
                    yield grand_child, grand_child_level

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
class ArgumentsList(ElementsList):
    dot: str
    parenthesized: Parenthesized

    @property
    def elements_list(self) -> DelimitedList:
        return self.parenthesized.content

    @property
    def elements(self) -> Sequence:
        return self.elements_list.elements


@dataclass
class OutputArguments(Composite):
    elements_list: DelimitedList
    whitespace_before_equal_sign: str
    equal_sign: str
    whitespace_after_equal_sign: str


@dataclass
class Call(Composite):
    identifer: Leaf
    arguments_list: ArgumentsList | None

    @property
    def arguments(self) -> Sequence:
        if self.arguments_list is None:
            return tuple()
        return self.arguments_list.elements


@dataclass
class Comment(Composite, Construct):
    marker: str
    content: str


@dataclass
class Operation(ElementsList):
    delimited_list: DelimitedList


@dataclass
class Parenthesized(Composite):
    opening_delimiter: str
    whitespace_before_content: str
    content: Component | str
    whitespace_after_content: str
    closing_delimiter: str


@dataclass
class Statement(Composite, Construct):
    output_arguments: OutputArguments | None
    body: Component
    whitespace_before_semicolon: str
    semicolon: str


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
    name: str
    element_delimiter: Any
    head: Any
    construct_delimiter: Any
    body: Component
    whitespace_before_end: str
    end_keyword: str
    whitespace_before_semicolon: str
    semicolon: str


class Function(Block):
    pass


class Class(Block):
    pass


class Properties(Block):
    pass


class Methods(Block):
    pass


class If(Block):

    def iterate_with_indent(self, level: int = 0) -> Generator[tuple[Component, int]]:
        for i, child in enumerate(self):
            if i == 4:
                level += 1
            if isinstance(child, Leaf) and child.value.startswith("else"):
                level -= 1
            if i == len(self) - 3:
                level += -1
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.iterate_with_indent(level):
                    yield grand_child, grand_child_level
            if isinstance(child, Leaf) and child.value.startswith("else"):
                level += 1


class ForLoop(Block):
    pass


class WhileLoop(Block):
    pass


class TryCatch(Block):
    pass


class Switch(Block):
    pass


class Case(Block):
    pass


class Otherwise(Block):
    pass


@dataclass
class File(Composite):
    leading_whitespace: str
    code: Code
    trailing_whitespace: str


@dataclass
class AnonymousFunction(Composite):
    at_sign: str
    white_space_before_arguments: str
    arguments_list: DelimitedList
    white_space_after_arguments: str
    expression: Component

    @property
    def arguments(self) -> list:
        return self.arguments_list.elements


@dataclass
class Array(ElementsList):
    parenthesized: Parenthesized
    # stuff: Any

    @property
    def elements_list(self) -> DelimitedList:
        return self.parenthesized.content

    @property
    def elements(self) -> list:
        return self.elements_list.elements if self.elements_list is not None else None


@dataclass
class SingleElementOperation(Composite):
    pass


@dataclass(eq=False)
class Command(VariableLengthComposite, Construct):
    pass


@dataclass
class Classdef(Block):
    pass


def none_or_whitespace(x) -> bool:
    return x is None or isinstance(x, str) and (x.isspace() or x == "")
