from __future__ import annotations
from dataclasses import dataclass, fields
from abc import ABC, abstractmethod
from typing import Sequence, Any, Type


class Component(ABC):
    """Base class for all code elements."""

    def __init__(self):

        # Parent is set in parent constructor.
        self.parent = None

    @property
    def successor(self) -> Any:
        if self.parent is None:
            raise ValueError("Component has no parent.")
        own_index = self.parent.index_of_child(self)
        successor_index = own_index + 1
        if successor_index >= len(self.parent):
            return None
        return self.parent[successor_index]

    @property
    def predecessor_index(self) -> int | None:
        if self.parent is None:
            raise ValueError("Component has no parent.")
        own_index = self.parent.index_of_child(self)
        if own_index > 0:
            return own_index - 1

    @property
    def predecessor(self) -> Any:
        if index := self.predecessor_index:
            return self.parent[index]

    @predecessor.setter
    def predecessor(self, value):
        if not isinstance(value, str):
            raise NotImplementedError("Only string is supported.")
        index = self.predecessor_index
        if index is None:
            raise ValueError("Component is first child of parent.")
        self.parent[index] = value

    def __iter__(self):
        return iter(())

    def iterate(self, types: Sequence | None = None):
        return iter(())

    def iterate_with_indent(self, level: int = 0) -> tuple[Component, int]:
        raise NotImplementedError()

    def __len__(self) -> int:
        return 1

    @abstractmethod
    def __str__(self) -> str:
        """Convert the code model to a code string."""


class Leaf(Component):
    """Component with no children."""

    def __init__(self, value: str):
        super().__init__()
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __getitem__(self, item: int):
        if item != 0:
            raise IndexError("Leaf has only one component.")
        return self.value

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}({self.value})"

    def __eq__(self, other) -> bool:
        return self.value == other.value

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        assert len(tokens) == 1
        return cls(tokens[0])


class Composite(Component):
    """
    Code element which has other Components as children.
    """

    def __init__(self, children: Sequence[Component | str]):
        super().__init__()
        self.children = children
        for child in self:
            if isinstance(child, Component):
                child.parent = self

    def __iter__(self):
        return iter(self.children)

    def __str__(self) -> str:
        strings = [str(child) for child in self if child is not None]
        return "".join(strings)

    def __getitem__(self, item: int):
        return self.children[item]

    def __setitem__(self, item: int, value):
        self.children[item] = value

    def __len__(self) -> int:
        return len(self.children)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"{name}({self.children})"

    def __eq__(self, other):
        """Elements are equal if they have equal type and their children are equal."""
        return (
            type(self) is type(other)
            and len(self) == len(other)
            and all(
                own_child == other_child for own_child, other_child in zip(self, other)
            )
        )

    def index_of_child(self, child: Component):
        for i, other in enumerate(self):
            if child is other:
                return i
        raise ValueError("Child not found.")

    def iterate(self, types: Sequence[Type] | None = None) -> Component:
        for child in self:
            if types is None or any(isinstance(child, type_) for type_ in types):
                yield child
            if any(isinstance(child, type_) for type_ in [Composite, Composite2]):
                for grand_child in child.iterate(types):
                    yield grand_child

    def iterate_with_indent(self, level: int = 0) -> tuple[Component, int]:
        for child in self:
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.iterate_with_indent(level):
                    yield grand_child, grand_child_level

    def pretty_string(
        self, indent_level: int = 0, compact: bool = False, nested: bool = True
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
        return cls(list(tokens))


@dataclass
class Composite2:

    def __iter__(self):
        return (getattr(self, f.name) for f in fields(self))

    def __str__(self) -> str:
        return "".join(map(str, self))

    def iterate(self, types: Sequence[Type] | None = None) -> Component:
        for child in self:
            if types is None or any(isinstance(child, type_) for type_ in types):
                yield child
            if any(isinstance(child, type_) for type_ in [Composite, Composite2]):
                for grand_child in child.iterate(types):
                    yield grand_child

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


class ArgumentsList(ElementsList):

    _PARENTHESIZED = 1

    @property
    def elements_list(self) -> DelimitedList:
        return self.children[self._PARENTHESIZED].content

    @property
    def elements(self):
        return self.elements_list.elements


@dataclass
class OutputArguments(Composite2):
    elements_list: DelimitedList
    whitespace_before_equal_sign: str
    equal_sign: str
    whitespace_after_equal_sign: str


class Call(Composite):

    _IDENTIFIER = 0
    _ARGUMENTS_LIST = 1

    @property
    def arguments_list(self) -> ArgumentsList | None:
        return self[self._ARGUMENTS_LIST]

    @property
    def arguments(self) -> Sequence:
        if self.arguments_list is None:
            return tuple()
        return self.arguments_list.elements


@dataclass
class Comment(Composite2, Construct):
    marker: str
    content: str


class Operation(ElementsList):

    @property
    def elements_list(self) -> DelimitedList:
        return self[0]


@dataclass
class Parenthesized(Composite2):
    opening_delimiter: str
    whitespace_before_content: str
    content: Component | str
    whitespace_after_content: str
    closing_delimiter: str


@dataclass
class Statement(Composite2, Construct):
    output_arguments: OutputArguments | None
    body: Component
    whitespace_before_semicolon: str
    semicolon: str


class Code(Composite):
    pass


class DelimitedList(Composite):

    @property
    def elements(self) -> list:
        return self.children[::2]

    @classmethod
    def build(
        cls,
        elements: Sequence[Composite | str],
        delimiter: str = ",",
        left_white: str = "",
        right_white: str = " ",
    ):
        tokens = [elements[0]]
        for element in elements[1:]:
            tokens += [left_white + delimiter + right_white, element]
        return cls(tokens)


@dataclass
class Block(Composite2, Construct):
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

    def iterate_with_indent(self, level: int = 0) -> tuple[Component, int]:
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
class File(Composite2):
    leading_whitespace: str
    code: Code
    trailing_whitespace: str


class AnonymousFunction(Composite):

    @property
    def arguments(self) -> list:
        if self.children[1] is None:
            return []
        delimited_list: DelimitedList = self.children[1]
        return delimited_list.elements

    @property
    def expression(self):
        return self.children[3]


class Array(ElementsList):

    _PARENTHESIZED = 0

    @property
    def elements_list(self) -> DelimitedList:
        return self[self._PARENTHESIZED].content

    @property
    def elements(self) -> list:
        return self.elements_list.elements if self.elements_list is not None else None


class SingleElementOperation(Composite):
    pass


class Command(Construct, Composite):
    pass


class Classdef(Block):
    pass


def none_or_whitespace(x) -> bool:
    return x is None or isinstance(x, str) and (x.isspace() or x == "")
