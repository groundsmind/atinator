# i didnt want to pull in pydantic for this Random bullshit go

import typing
from typing import cast, Any, TypeAliasType, Self, ClassVar
from types import GenericAlias

import dataclasses
from dataclasses import dataclass, MISSING

from collections.abc import Collection, Generator

import re
import os

class OptionParseError(ValueError):
    def __init__(self, env_name: str, cause: BaseException):
        self.env_name = env_name
        self.__cause__ = cause
        super().__init__(f"while parsing option {env_name!r}")

class ConfigParseError(ExceptionGroup[OptionParseError]): pass

def _resolve_alias(type_: type | TypeAliasType) -> type:
    temp = type_
    while isinstance(temp, TypeAliasType):
        temp = temp.__value__
    if not isinstance(temp, type):
        raise TypeError(f"{type_!r} is not a type or cannot resolve to one")
    return temp

@dataclass
class ConfigBase:
    _bool_strs: ClassVar[tuple[Collection[str], Collection[str]]] = (
        {"false", "off", "no", "0"},
        {"true", "on", "yes", "1"},
    )

    @classmethod
    def _split(cls, str_: str) -> Generator[str]:
        return (
            cast(str, p).replace("\\,", ",") # type: ignore
            for p in re.split(r"(?<!\\),", str_)
        )

    @classmethod
    def _str_to_value(cls, str_: str, type_: type | TypeAliasType | GenericAlias) -> Any:
        if isinstance(type_, TypeAliasType):
            type_ = _resolve_alias(type_)

        if type_ is str: return str_
        if type_ is int or type_ is float: return type_(str_)
        if type_ is bool:
            str_cf = str_.casefold()
            if str_cf in cls._bool_strs[0]: return False
            if str_cf in cls._bool_strs[1]: return True
            raise ValueError(f"invalid bool value {str_!r} (valid: {cls._bool_strs[0]!r}; {cls._bool_strs[1]!r})")

        origin_raw = typing.get_origin(type_)
        if origin_raw is not None:
            origin = _resolve_alias(origin_raw)
            args = typing.get_args(type_)

            if (
                origin is list or origin is set or origin is frozenset or
                origin is tuple and len(args) == 2 and args[1] is Ellipsis
            ):
                item_type = _resolve_alias(args[0])
                return origin(
                    cls._str_to_value(value, item_type)
                    for value in cls._split(str_)
                ) # type: ignore

            if origin is tuple:
                return origin(
                    cls._str_to_value(value, _resolve_alias(arg))
                    for value, arg in zip(cls._split(str_), args, strict=True)
                ) # type: ignore

        raise TypeError(f"type {type_!r} is not supported")

    @classmethod
    def from_env(cls) -> Self:
        kwargs: dict[str, Any] = {}
        excs: list[OptionParseError] = []
        for field in dataclasses.fields(cls):
            name = field.name
            type_ = field.type
            env_name = name.upper()

            str_ = os.getenv(env_name)
            try:
                if str_ is None:
                    if field.default is MISSING:
                        raise KeyError(f"required environment variable {env_name!r} not found")
                    value = None
                else:
                    if not isinstance(type_, (type, TypeAliasType, GenericAlias)):
                        raise TypeError(f"dataclass field {name!r} has invalid annotation {type_!r} of type {type(type_).__qualname__!r}")

                    value = cls._str_to_value(str_, type_)

                kwargs[name] = value
            except Exception as exc:
                excs.append(OptionParseError(env_name, exc))

        if len(excs) != 0:
            raise ConfigParseError("failed to parse one or more config options", excs)
        return cls(**kwargs)