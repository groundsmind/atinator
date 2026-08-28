from sqlalchemy import JSON, BigInteger, DateTime, Index, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime

class Base(AsyncAttrs, DeclarativeBase):
    def __repr__(self):
        mapper = inspect(self.__class__)
        values = ", ".join(
            f"{col.name}={getattr(self, col.name)!r}"
            for col in mapper.columns
        )
        return f"{self.__class__.__name__}({values})"

class GuildData(Base):
    __tablename__ = "guild_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger)
    someone_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    member_bag_all: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=MutableList
    )
    member_bag: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=MutableList
    )

class Optout(Base):
    __tablename__ = "optout"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

class Ping(Base):
    __tablename__ = "ping"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    someone_id: Mapped[int] = mapped_column(BigInteger, index=True)
    author_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    time: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        Index("ping_someone_id_guild_id_idx", guild_id, someone_id),
    )