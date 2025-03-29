from __future__ import annotations
from typing import Sequence, Any


class Component:
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

    def iterate(self, types: Sequence):
        return iter(())

    def iterate_with_indent(self, level: int = 0) -> tuple[Component, int]:
        raise NotImplementedError()

    def __len__(self) -> int:
        return 1


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
    """Code element which has other Components as children."""

    def __init__(self, children: list[Component]):
        super().__init__()
        self.children = children
        for child in self:
            if isinstance(child, Component):
                child.parent = self

    def __iter__(self):
        return iter(self.children)

    def __str__(self):
        return "".join(str(tok) for tok in self if tok is not None)

    def __getitem__(self, item: int):
        return self.children[item]

    def __setitem__(self, item: int, value):
        self.children[item] = value

    def __len__(self):
        return len(self.children)

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}({self.children})"

    def __eq__(self, other):
        """Elements are equal if they have equal type and their children are equal."""
        return (
            type(self) == type(other)
            and len(self) == len(other)
            and all(own_child == other_child for own_child, other_child in zip(self, other))
        )

    def index_of_child(self, child: Component):
        for i, other in enumerate(self):
            if child is other:
                return i
        raise ValueError("Child not found.")

    def iterate(self, types: Sequence) -> Component:
        for child in self:
            if any(isinstance(child, type_) for type_ in types):
                yield child
            if isinstance(child, Composite):
                for grand_child in child.iterate(types):
                    yield grand_child

    def iterate_with_indent(self, level: int = 0) -> tuple[Component, int]:
        for child in self:
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.iterate_with_indent(level):
                    yield grand_child, grand_child_level

    def pretty_string(self, indent_level: int = 0, compact: bool = False, nested: bool = True) -> str:
        indent = indent_level * 4 * " "
        type_ = self.__class__.__name__

        head = f"{type_}(["
        tail = f"])"

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
        body = '\n'.join(body_parts)
        return f"{indent}{head}\n{body}\n{indent}{tail}"

    def to_list(self) -> list:
        return [c.to_list() if isinstance(c, Composite) else c for c in self]

    def to_repr_list(self) -> list:
        return [c.to_repr_list() if isinstance(c, Composite) else c for c in self]

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        return cls(list(tokens))


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

    _PARENTHESIZED = 0

    @property
    def elements_list(self) -> DelimitedList:
        return self.children[self._PARENTHESIZED].content

    @property
    def elements(self):
        return self.elements_list.elements


class OutputArguments(ElementsList):

    _PARENTHESIZED = 0

    @property
    def elements_list(self) -> DelimitedList:
        return self.children[self._PARENTHESIZED].content

    @property
    def elements(self):
        return self.elements_list.elements


class Call(Composite):

    _IDENTIFIER = 0
    _ARGUMENTS_LIST = 1

    @property
    def arguments_list(self) -> ArgumentsList | None:
        return self.children[self._ARGUMENTS_LIST]

    @property
    def arguments(self) -> Sequence:
        if self.arguments_list is None:
            return tuple()
        delimited_list: DelimitedList = self.children[1]
        return delimited_list.elements


class Comment(Composite, Construct):

    _PERCENTAGE_SIGN = 0
    _STRING = 1

    @property
    def string(self):
        return self[self._STRING]


class Operation(Composite):
    pass


class ParenthesizedOperation(Composite):
    pass


class Parenthesized(Composite):

    # 0: Bracket
    # 1: Whitespace
    # 2: Content
    # 3: Whitespace
    # 4: Bracket

    @property
    def content(self) -> Any:
        return self.children[2]


class Statement(Composite, Construct):

    _OUTPUT_ARGUMENTS = 0
    _BODY = 1

    @property
    def output_arguments(self) -> Sequence:
        output_args_list = self[self._OUTPUT_ARGUMENTS]
        if output_args_list is None:
            return tuple()
        return output_args_list.elements

    @property
    def body(self):
        return self[self._BODY]


class Code(Composite):
    pass


class DelimitedList(Composite):

    @property
    def elements(self) -> list:
        return self.children[::2]

    @classmethod
    def build(cls, elements: Sequence[Composite | str], delimiter: str = ",", left_white: str = "", right_white: str = " "):
        tokens = [elements[0]]
        for element in elements[1:]:
            tokens += [left_white + delimiter + right_white, element]
        return cls(tokens)


class Block(Composite, Construct):

    @property
    def head(self) -> Component:
        return self.children[2]

    @property
    def body(self) -> Component:
        return self.children[4]

    def iterate_with_indent(self, level: int = 0) -> tuple[Component, int]:
        for i, child in enumerate(self):
            if i == 4:
                level += 1
            if i == 5:
                level += -1
            yield child, level
            if isinstance(child, Composite):
                for grand_child, grand_child_level in child.iterate_with_indent(level):
                    yield grand_child, grand_child_level


class Function(Block):
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


class TryCatch(Block):
    pass


class File(Composite):
    pass


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
        return self.children[self._PARENTHESIZED].content

    @property
    def elements(self) -> list:
        return self.elements_list.elements if self.elements_list is not None else None


class SingleElementOperation(Composite):
    pass


def none_or_whitespace(x) -> bool:
    return x is None or isinstance(x, str) and (x.isspace() or x == "")